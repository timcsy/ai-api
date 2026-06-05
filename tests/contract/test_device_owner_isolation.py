"""Phase 19 US1 — device-flow owner isolation (T011).

Unauthenticated cannot read/approve a device request; a member cannot approve a
request against another member's allocation (403, and nothing is minted).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER
from ai_api.db import get_sessionmaker
from ai_api.services.allocations import AllocationService


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


async def _login_member_with_allocation(
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
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    me = (await client.get("/me")).json()
    alloc = (
        await client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    return alloc["id"]


@pytest.mark.asyncio
async def test_unauthenticated_cannot_read_or_approve(app_client: AsyncClient) -> None:
    auth = (await app_client.post("/device/authorize", json={})).json()
    # No session cookie set yet → read path is 401.
    assert (await app_client.get(f"/me/device/{auth['user_code']}")).status_code == 401
    # Mutating path is also rejected for an unauthenticated caller; CSRF (403) is
    # evaluated before the session check (consistent with every other mutating
    # member endpoint), so accept either rejection — the point is it cannot approve.
    approve_status = (
        await app_client.post(
            f"/me/device/{auth['user_code']}/approve",
            headers=_csrf(app_client),
            json={"allocation_ids": ["x"]},
        )
    ).status_code
    assert approve_status in (401, 403)


@pytest.mark.asyncio
async def test_member_cannot_approve_others_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Bob owns an allocation.
    bob_alloc = await _login_member_with_allocation(app_client, admin_headers, "bob@x.com")
    # Alice logs in (session now Alice) and starts a device request.
    await _login_member_with_allocation(app_client, admin_headers, "alice@x.com")
    auth = (await app_client.post("/device/authorize", json={})).json()

    # Alice tries to approve binding BOB's allocation → 403, nothing minted.
    r = await app_client.post(
        f"/me/device/{auth['user_code']}/approve",
        headers=_csrf(app_client),
        json={"allocation_ids": [bob_alloc]},
    )
    assert r.status_code == 403

    sm = get_sessionmaker()
    async with sm() as s:
        creds = await AllocationService(s).list_credentials(bob_alloc)
        assert len(list(creds)) == 1  # only Bob's default — no device-flow mint
