"""Contract tests for /admin/allocations/{id}/usage-timeseries."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_404_unknown_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ/usage-timeseries"
        "?bucket=day&from=2026-05-01T00:00:00Z&to=2026-05-31T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_hour_bucket_too_wide_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Create an allocation first so the 404 check passes
    alloc = (await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "u@x.com", "resource_model": "gpt-4o-mini"},
    )).json()
    r = await app_client.get(
        f"/admin/allocations/{alloc['id']}/usage-timeseries"
        "?bucket=hour&from=2026-05-01T00:00:00Z&to=2026-05-20T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "range_too_wide_for_bucket"


@pytest.mark.asyncio
async def test_empty_timeseries_200(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = (await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "u@x.com", "resource_model": "gpt-4o-mini"},
    )).json()
    r = await app_client.get(
        f"/admin/allocations/{alloc['id']}/usage-timeseries"
        "?bucket=day&from=2026-05-01T00:00:00Z&to=2026-05-31T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["allocation_id"] == alloc["id"]
    assert body["bucket"] == "day"
    assert body["points"] == []
