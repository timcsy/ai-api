"""Contract tests for require_admin dep (Phase 3b.2 c-β additive)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import Member, MemberStatus


async def _promote(member_id: str, is_admin: bool = True) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        m = await s.get(Member, member_id)
        if m:
            m.is_admin = is_admin
            await s.commit()


async def _disable(member_id: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        m = await s.get(Member, member_id)
        if m:
            m.status = MemberStatus.disabled
            await s.commit()


async def _create_and_login(
    client: AsyncClient, admin_headers: dict[str, str], email: str
) -> str:
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
    me_before = await client.get("/me")
    if me_before.status_code != 200:
        await client.post(
            "/auth/local/login", json={"email": email, "password": "VerySafePass123"}
        )
    me = (await client.get("/me")).json()
    return me["id"]


@pytest.mark.asyncio
async def test_admin_token_path_works(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get("/admin/members", headers=admin_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_session_with_admin_works(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    mid = await _create_and_login(app_client, admin_headers, "alice@x.com")
    await _promote(mid, True)
    # Session cookie now belongs to an admin member
    r = await app_client.get("/admin/members")  # no X-Admin-Token
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_session_without_admin_is_403(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _create_and_login(app_client, admin_headers, "bob@x.com")
    r = await app_client.get("/admin/members")
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "not_admin"


@pytest.mark.asyncio
async def test_disabled_admin_session_is_rejected(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Disabling a Member invalidates their session (Phase 2 SC-006), so the
    auth dep cannot resolve a member — falls through to 401 unauthorized.

    This is the desired security posture: a disabled admin is locked out
    immediately, no graceful 403."""
    mid = await _create_and_login(app_client, admin_headers, "carol@x.com")
    await _promote(mid, True)
    await _disable(mid)
    r = await app_client.get("/admin/members")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_at_all_is_401(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/members")
    assert r.status_code == 401
    assert r.json()["detail"]["error"]["code"] == "unauthorized"
