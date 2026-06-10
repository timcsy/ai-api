"""Contract tests for /admin/members."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_local_member_with_invitation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": "bob@partner.com",
            "provider": "local_password",
            "send_invitation": True,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "bob@partner.com"
    assert body["provider"] == "local_password"
    assert body["has_password"] is False
    assert "invitation_url" in body
    assert "/auth/invitation/" in body["invitation_url"]


@pytest.mark.asyncio
async def test_create_local_member_with_initial_password(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": "bob@partner.com",
            "provider": "local_password",
            "send_invitation": False,
            "initial_password": "VerySafePass123",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["has_password"] is True
    assert "invitation_url" not in body


@pytest.mark.asyncio
async def test_create_external_member(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/members",
        headers=admin_headers,
        json={"email": "svc@example.com", "provider": "external"},
    )
    assert r.status_code == 201
    assert r.json()["provider"] == "external"


@pytest.mark.asyncio
async def test_create_member_duplicate_email_409(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    payload = {"email": "alice@example.com", "provider": "external"}
    r1 = await app_client.post("/admin/members", headers=admin_headers, json=payload)
    assert r1.status_code == 201
    r2 = await app_client.post("/admin/members", headers=admin_headers, json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_and_get_member(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={"email": "alice@example.com", "provider": "external"},
        )
    ).json()
    r = await app_client.get("/admin/members", headers=admin_headers)
    assert any(m["id"] == created["id"] for m in r.json())

    r = await app_client.get(f"/admin/members/{created['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_patch_member_status(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={"email": "alice@example.com", "provider": "external"},
        )
    ).json()
    r = await app_client.patch(
        f"/admin/members/{created['id']}",
        headers=admin_headers,
        json={"status": "disabled"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    assert r.json()["disabled_at"] is not None


@pytest.mark.asyncio
async def test_delete_member_with_allocations_safe_deletes(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Phase 30 behaviour change: a member with allocations is now SAFE-deleted
    (allocations/credentials removed, usage orphan-retained) instead of blocked
    with 409. See specs/039-member-batch-admin."""
    created = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={"email": "alice@example.com", "provider": "external"},
        )
    ).json()
    # Create an allocation against this Member
    await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"member_id": created["id"], "resource_model": "gpt-4o-mini"},
    )
    r = await app_client.delete(f"/admin/members/{created['id']}", headers=admin_headers)
    assert r.status_code == 204
    # member is gone
    assert (
        await app_client.get(f"/admin/members/{created['id']}", headers=admin_headers)
    ).status_code == 404


@pytest.mark.asyncio
async def test_delete_member_no_allocations(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={"email": "alice@example.com", "provider": "external"},
        )
    ).json()
    r = await app_client.delete(f"/admin/members/{created['id']}", headers=admin_headers)
    assert r.status_code == 204
