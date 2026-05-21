"""Contract tests for DELETE /admin/allocations/{id}."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "bob@example.com", "resource_model": "gpt-4o-mini"},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_revoke_200(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _create(app_client, admin_headers)
    r = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "revoked"
    assert body["revoked_at"] is not None


@pytest.mark.asyncio
async def test_revoke_is_idempotent(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _create(app_client, admin_headers)
    first = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    second = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "revoked"
    # revoked_at must not change on the second call (strip any tz suffix differences from sqlite)
    from datetime import datetime
    a = datetime.fromisoformat(first.json()["revoked_at"].replace("Z", "+00:00"))
    b = datetime.fromisoformat(second.json()["revoked_at"].replace("Z", "+00:00"))
    assert a.replace(tzinfo=None) == b.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_revoke_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.delete(
        "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ", headers=admin_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_revoke_requires_admin(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _create(app_client, admin_headers)
    r = await app_client.delete(f"/admin/allocations/{alloc['id']}")
    assert r.status_code == 401
