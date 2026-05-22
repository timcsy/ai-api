"""Contract + integration tests for quarantine flow."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import Allocation, AllocationStatus


async def _make_allocation(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "u@x.com", "resource_model": "gpt-4o-mini"},
    )
    return r.json()


async def _force_quarantine(allocation_id: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        alloc = (
            await s.execute(select(Allocation).where(Allocation.id == allocation_id))
        ).scalar_one()
        alloc.status = AllocationStatus.quarantined
        await s.commit()


@pytest.mark.asyncio
async def test_unquarantine_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ/unquarantine",
        headers=admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unquarantine_409_when_active(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    r = await app_client.post(
        f"/admin/allocations/{alloc['id']}/unquarantine", headers=admin_headers
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "not_quarantined"


@pytest.mark.asyncio
async def test_unquarantine_200_restores_active(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    await _force_quarantine(alloc["id"])
    r = await app_client.post(
        f"/admin/allocations/{alloc['id']}/unquarantine", headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_proxy_rejects_quarantined_403(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    await _force_quarantine(alloc["id"])
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "allocation_quarantined"
