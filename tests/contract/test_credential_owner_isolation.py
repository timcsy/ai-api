"""Phase 20 US5 — owner isolation + admin governance of application keys."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.api.deps import CSRF_HEADER
from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog


def _csrf(c: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: c.cookies.get("aiapi_csrf") or ""}


async def _login(c: AsyncClient, admin: dict[str, str], email: str) -> str:
    await c.post(
        "/admin/members", headers=admin,
        json={"email": email, "provider": "local_password", "initial_password": "VerySafePass123", "send_invitation": False},
    )
    await c.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return (await c.get("/me")).json()["id"]


async def _alloc(c: AsyncClient, admin: dict[str, str], mid: str, model: str) -> str:
    return (await c.post("/admin/allocations", headers=admin, json={"member_id": mid, "resource_model": model})).json()["id"]


async def _key(c: AsyncClient, allocs: list[str]) -> str:
    return (await c.post("/me/credentials", headers=_csrf(c), json={"name": "k", "allocation_ids": allocs})).json()["id"]


@pytest.mark.asyncio
async def test_member_cannot_touch_others_key(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    bob = await _login(app_client, admin_headers, "bob@x.com")
    ba = await _alloc(app_client, admin_headers, bob, "gpt-4o-mini")
    bob_key = await _key(app_client, [ba])
    # Switch to alice.
    await _login(app_client, admin_headers, "alice@x.com")
    assert (await app_client.patch(f"/me/credentials/{bob_key}", headers=_csrf(app_client), json={"remove": [ba]})).status_code == 404
    assert (await app_client.request("DELETE", f"/me/credentials/{bob_key}", headers=_csrf(app_client))).status_code == 404


@pytest.mark.asyncio
async def test_admin_lists_and_revokes_any_member_key(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    bob = await _login(app_client, admin_headers, "bob@x.com")
    ba = await _alloc(app_client, admin_headers, bob, "gpt-4o-mini")
    bob_key = await _key(app_client, [ba])

    lst = await app_client.get(f"/admin/members/{bob}/credentials", headers=admin_headers)
    assert lst.status_code == 200
    assert any(k["id"] == bob_key for k in lst.json())

    d = await app_client.request("DELETE", f"/admin/credentials/{bob_key}", headers=admin_headers)
    assert d.status_code == 204
    # Unauthenticated admin path → 401.
    assert (await app_client.get(f"/admin/members/{bob}/credentials")).status_code in (401, 403)

    sm = get_sessionmaker()
    async with sm() as s:
        rows = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.credential_revoked,
                    AuthAuditLog.target_id == bob_key,
                )
            )
        ).scalars().all()
        assert len(rows) == 1
