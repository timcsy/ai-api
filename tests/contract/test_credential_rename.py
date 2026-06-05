"""Phase 21 US2 — rename an application key (label only; no token/scope change)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.api.deps import CSRF_HEADER
from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog


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


async def _call(c: AsyncClient, token: str, model: str) -> int:
    with patch("ai_api.proxy.upstream.acompletion") as m:
        m.return_value = _stub(model)
        r = await c.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
        )
    return r.status_code


@pytest.mark.asyncio
async def test_rename_does_not_affect_token_or_scope(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    created = (
        await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "預設", "allocation_ids": [a, b]})
    ).json()
    cid, token = created["id"], created["token"]

    r = await app_client.patch(f"/me/credentials/{cid}", headers=_csrf(app_client), json={"name": "我的筆電"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "我的筆電"
    assert {al["resource_model"] for al in r.json()["allocations"]} == {"gpt-4o-mini", "gpt-4o"}
    # token unaffected, both models still callable.
    assert await _call(app_client, token, "gpt-4o-mini") == 200
    assert await _call(app_client, token, "gpt-4o") == 200


@pytest.mark.asyncio
async def test_rename_with_scope_change_together(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "carol@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    created = (await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "k", "allocation_ids": [a]})).json()
    cid, token = created["id"], created["token"]
    r = await app_client.patch(f"/me/credentials/{cid}", headers=_csrf(app_client), json={"name": "renamed", "add": [b]})
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"
    assert await _call(app_client, token, "gpt-4o") == 200  # add took effect too


@pytest.mark.asyncio
async def test_rename_empty_name_rejected(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "dora@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    cid = (await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "k", "allocation_ids": [a]})).json()["id"]
    bad = await app_client.patch(f"/me/credentials/{cid}", headers=_csrf(app_client), json={"name": ""})
    assert bad.status_code in (400, 422)


@pytest.mark.asyncio
async def test_admin_rename_audited_and_owner_isolation(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    bob = await _login(app_client, admin_headers, "bob@x.com")
    ba = await _alloc(app_client, admin_headers, bob, "gpt-4o-mini")
    bob_key = (await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "k", "allocation_ids": [ba]})).json()["id"]
    # Alice cannot rename Bob's key.
    await _login(app_client, admin_headers, "alice@x.com")
    assert (await app_client.patch(f"/me/credentials/{bob_key}", headers=_csrf(app_client), json={"name": "hax"})).status_code in (403, 404)

    # Admin can, and it is audited.
    r = await app_client.patch(f"/admin/credentials/{bob_key}", headers=admin_headers, json={"name": "admin-renamed"})
    assert r.status_code == 200 and r.json()["name"] == "admin-renamed"
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.credential_renamed,
                    AuthAuditLog.target_id == bob_key,
                )
            )
        ).scalars().all()
        assert len(rows) == 1
