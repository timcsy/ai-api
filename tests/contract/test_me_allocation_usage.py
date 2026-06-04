"""Contract tests: per-allocation usage charts for the member (timeseries + heatmap).

A member can see daily timeseries + weekday x hour heatmap for THEIR OWN allocation;
they get 403 for another member's allocation (owner isolation).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER


def _stub() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


async def _login_with_allocation(
    client: AsyncClient, admin_headers: dict[str, str], email: str
) -> tuple[str, str]:
    await client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": email,
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    me = (await client.get("/me")).json()
    alloc = (
        await client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    return alloc["id"], alloc["token"]


@pytest.mark.asyncio
async def test_allocation_timeseries_and_heatmap_reflect_calls(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id, token = await _login_with_allocation(app_client, admin_headers, "alice@x.com")
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        for _ in range(2):
            r = await app_client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert r.status_code == 200

    ts = await app_client.get(f"/me/allocations/{alloc_id}/usage/timeseries")
    assert ts.status_code == 200
    tsb = ts.json()
    assert tsb["bucket"] == "day"
    assert sum(p["tokens"] for p in tsb["points"]) == 16  # 2 calls x 8 tokens

    hm = await app_client.get(f"/me/allocations/{alloc_id}/usage/heatmap")
    assert hm.status_code == 200
    hmb = hm.json()
    assert hmb["timezone"] == "UTC+8"
    assert sum(c["tokens"] for c in hmb["cells"]) == 16
    assert sum(c["call_count"] for c in hmb["cells"]) == 2


@pytest.mark.asyncio
async def test_allocation_usage_owner_isolation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    bob_alloc, _ = await _login_with_allocation(app_client, admin_headers, "bob@x.com")
    # Switch session to alice.
    await _login_with_allocation(app_client, admin_headers, "alice@x.com")

    assert (
        await app_client.get(f"/me/allocations/{bob_alloc}/usage/timeseries")
    ).status_code == 403
    assert (
        await app_client.get(f"/me/allocations/{bob_alloc}/usage/heatmap")
    ).status_code == 403
