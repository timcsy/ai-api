"""Contract tests for PATCH /admin/allocations/{id} (quota + service flag)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _make_alloc(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "u@x.com", "resource_model": "gpt-4o-mini"},
    )
    return r.json()


@pytest.mark.asyncio
async def test_patch_quota_set(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _make_alloc(app_client, admin_headers)
    r = await app_client.patch(
        f"/admin/allocations/{a['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": 1000},
    )
    assert r.status_code == 200
    assert r.json()["quota_tokens_per_month"] == 1000


@pytest.mark.asyncio
async def test_patch_quota_unlimited(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _make_alloc(app_client, admin_headers)
    # First set, then clear
    await app_client.patch(
        f"/admin/allocations/{a['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": 1000},
    )
    r = await app_client.patch(
        f"/admin/allocations/{a['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": None},
    )
    assert r.status_code == 200
    assert r.json()["quota_tokens_per_month"] is None


@pytest.mark.asyncio
async def test_patch_is_service_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    a = await _make_alloc(app_client, admin_headers)
    r = await app_client.patch(
        f"/admin/allocations/{a['id']}",
        headers=admin_headers,
        json={"is_service_allocation": True},
    )
    assert r.status_code == 200
    assert r.json()["is_service_allocation"] is True


@pytest.mark.asyncio
async def test_patch_unknown_field_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    a = await _make_alloc(app_client, admin_headers)
    r = await app_client.patch(
        f"/admin/allocations/{a['id']}",
        headers=admin_headers,
        json={"bogus_field": 123},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_negative_quota_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    a = await _make_alloc(app_client, admin_headers)
    r = await app_client.patch(
        f"/admin/allocations/{a['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": -1},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.patch(
        "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ",
        headers=admin_headers,
        json={"quota_tokens_per_month": 100},
    )
    assert r.status_code == 404
