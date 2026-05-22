"""Contract tests for /admin/usage.csv and /admin/usage.json."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_csv_content_type(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/usage.csv?group_by=member&from=2026-05-01T00:00:00Z&to=2026-05-31T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    # Header row at minimum
    assert "group_key" in r.text


@pytest.mark.asyncio
async def test_json_export_content_type(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/usage.json?group_by=member&from=2026-05-01T00:00:00Z&to=2026-05-31T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_csv_range_too_wide_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/usage.csv?group_by=member&from=2026-01-01T00:00:00Z&to=2026-06-01T00:00:00Z",
        headers=admin_headers,
    )
    assert r.status_code == 400
