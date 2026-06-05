"""Phase 20 US6 — Codex device-flow can be authorised over MULTIPLE allocations,
minting one application key that spans those models."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER


def _csrf(c: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: c.cookies.get("aiapi_csrf") or ""}


def _stub(model: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _login(c: AsyncClient, admin: dict[str, str], email: str) -> str:
    await c.post(
        "/admin/members", headers=admin,
        json={"email": email, "provider": "local_password", "initial_password": "VerySafePass123", "send_invitation": False},
    )
    await c.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return (await c.get("/me")).json()["id"]


async def _alloc(c: AsyncClient, admin: dict[str, str], mid: str, model: str) -> str:
    return (await c.post("/admin/allocations", headers=admin, json={"member_id": mid, "resource_model": model})).json()["id"]


@pytest.mark.asyncio
async def test_device_flow_approve_multiple_allocations(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o")

    auth = (await app_client.post("/device/authorize", json={"device_label": "Codex"})).json()
    appr = await app_client.post(
        f"/me/device/{auth['user_code']}/approve", headers=_csrf(app_client), json={"allocation_ids": [a, b]}
    )
    assert appr.status_code == 204, appr.text
    tok = (await app_client.post("/device/token", json={"device_code": auth["device_code"]})).json()

    # The single minted key spans both models.
    for model in ("gpt-4o-mini", "gpt-4o"):
        with patch("ai_api.proxy.upstream.acompletion") as m:
            m.return_value = _stub(model)
            r = await app_client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {tok['token']}"},
                json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
            )
        assert r.status_code == 200, (model, r.text)


@pytest.mark.asyncio
async def test_device_flow_approve_rejects_others_allocation(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    bob = await _login(app_client, admin_headers, "bob@x.com")
    bob_alloc = await _alloc(app_client, admin_headers, bob, "gpt-4o-mini")
    alice = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, alice, "gpt-4o")
    auth = (await app_client.post("/device/authorize", json={})).json()
    r = await app_client.post(
        f"/me/device/{auth['user_code']}/approve", headers=_csrf(app_client), json={"allocation_ids": [a, bob_alloc]}
    )
    assert r.status_code == 403
