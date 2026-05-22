"""Contract tests for /admin/usage."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_params_422(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/usage", headers=admin_headers)
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_invalid_time_range_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/usage?group_by=member&from=2026-05-15T00:00:00Z&to=2026-05-01T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "invalid_time_range"


@pytest.mark.asyncio
async def test_range_too_wide_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/usage?group_by=member&from=2026-01-01T00:00:00Z&to=2026-12-31T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "range_too_wide"


@pytest.mark.asyncio
async def test_unauthorized_401(app_client: AsyncClient) -> None:
    r = await app_client.get(
        "/admin/usage?group_by=member&from=2026-05-01T00:00:00Z&to=2026-05-31T00:00:00Z"
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_empty_db_returns_empty_items(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/usage?group_by=member&from=2026-05-01T00:00:00Z&to=2026-05-31T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "member"
    assert body["items"] == []
