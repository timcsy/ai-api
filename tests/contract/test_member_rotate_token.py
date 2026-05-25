"""Contract test: POST /me/allocations/{id}/rotate-token (Phase 3b.2 hotfix++)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER


async def _login_and_get_allocation(
    client: AsyncClient, admin_headers: dict[str, str]
) -> tuple[str, str, str]:
    """Create member, login, create allocation. Returns (member_id, allocation_id, original_token)."""
    await client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": "alice@x.com",
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    await client.post(
        "/auth/local/login", json={"email": "alice@x.com", "password": "VerySafePass123"}
    )
    me = (await client.get("/me")).json()
    alloc = (
        await client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    return me["id"], alloc["id"], alloc["token"]


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    csrf = client.cookies.get("aiapi_csrf") or ""
    return {CSRF_HEADER: csrf}


@pytest.mark.asyncio
async def test_rotate_returns_new_token_and_invalidates_old(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    _, alloc_id, old_token = await _login_and_get_allocation(app_client, admin_headers)

    r = await app_client.post(
        f"/me/allocations/{alloc_id}/rotate-token", headers=_csrf_headers(app_client)
    )
    assert r.status_code == 200
    body = r.json()
    assert "token" in body
    assert body["token"] != old_token
    assert body["token_prefix"] != ""

    # Old token should NOT work for proxy auth
    r2 = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {old_token}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_rotate_forbids_other_members_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Create bob's allocation
    await app_client.post(
        "/admin/members",
        headers=admin_headers,
        json={"email": "bob@x.com", "provider": "external", "send_invitation": False},
    )
    bob_id = (await app_client.get("/admin/members?email=bob@x.com", headers=admin_headers)).json()[
        0
    ]["id"]
    bob_alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": bob_id, "resource_model": "gpt-4o-mini"},
        )
    ).json()

    # Login as alice
    _, _alice_alloc, _ = await _login_and_get_allocation(app_client, admin_headers)

    # alice tries to rotate bob's allocation
    r = await app_client.post(
        f"/me/allocations/{bob_alloc['id']}/rotate-token",
        headers=_csrf_headers(app_client),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rotate_requires_csrf(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    _, alloc_id, _ = await _login_and_get_allocation(app_client, admin_headers)
    r = await app_client.post(f"/me/allocations/{alloc_id}/rotate-token")  # no CSRF
    assert r.status_code == 403
