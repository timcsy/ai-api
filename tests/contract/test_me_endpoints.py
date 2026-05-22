"""Contract tests for /me, /me/allocations, /me/allocations/{id}/calls."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _make_local_and_login(
    client: AsyncClient, admin_headers: dict[str, str], email: str = "u@x.com"
) -> AsyncClient:
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
    r = await client.post(
        "/auth/local/login", json={"email": email, "password": "VerySafePass123"}
    )
    assert r.status_code == 200
    return client


@pytest.mark.asyncio
async def test_me_401_without_session(app_client: AsyncClient) -> None:
    r = await app_client.get("/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_200_after_login(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/me")
    assert r.status_code == 200
    assert r.json()["email"] == "u@x.com"


@pytest.mark.asyncio
async def test_me_allocations(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _make_local_and_login(app_client, admin_headers)
    me = (await app_client.get("/me")).json()
    # Admin creates an allocation for this Member
    await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
    )
    r = await app_client.get("/me/allocations")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["member_id"] == me["id"]


@pytest.mark.asyncio
async def test_cross_member_allocation_calls_403(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Alice logs in
    await _make_local_and_login(app_client, admin_headers, email="alice@x.com")
    # Admin makes a Member for Bob and assigns an allocation
    bob = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={"email": "bob@x.com", "provider": "external"},
        )
    ).json()
    bobs_alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": bob["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    # Alice still has session; she should NOT see Bob's allocation calls
    r = await app_client.get(f"/me/allocations/{bobs_alloc['id']}/calls")
    assert r.status_code == 403
