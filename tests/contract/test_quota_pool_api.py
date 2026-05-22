"""Contract tests for Phase 3c admin quota-pool endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.config import get_settings


@pytest.mark.asyncio
async def test_status_disabled(app_client: AsyncClient, admin_headers, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "0")
    get_settings.cache_clear()
    r = await app_client.get("/admin/quota-pool/status", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_T"] == 0
    assert body["settings"]["enabled"] is False
    assert body["last_rebalance_at"] is None


@pytest.mark.asyncio
async def test_status_unauthorized(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/quota-pool/status")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_manual_trigger_pool_disabled(
    app_client: AsyncClient, admin_headers, monkeypatch
) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "0")
    get_settings.cache_clear()
    r = await app_client.post("/admin/quota-pool/rebalance", headers=admin_headers)
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "pool_disabled"


@pytest.mark.asyncio
async def test_manual_trigger_pool_idle(
    app_client: AsyncClient, admin_headers, monkeypatch
) -> None:
    """T enabled but no pool members → pool_idle."""
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    get_settings.cache_clear()
    r = await app_client.post("/admin/quota-pool/rebalance", headers=admin_headers)
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "pool_idle"


@pytest.mark.asyncio
async def test_rebalance_log_404(app_client: AsyncClient, admin_headers) -> None:
    r = await app_client.get(
        f"/admin/quota-pool/rebalance-log/{ULID()}", headers=admin_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_rebalance_log_list_empty(
    app_client: AsyncClient, admin_headers
) -> None:
    r = await app_client.get("/admin/quota-pool/rebalance-log", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_manual_trigger_success_returns_summary(
    app_client: AsyncClient, admin_headers, monkeypatch
) -> None:
    """End-to-end: create allocation, set T, trigger rebalance, check log + status."""
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    # Create an allocation via the API
    alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "u@x.com", "resource_model": "gpt-4o-mini"},
        )
    ).json()

    r = await app_client.post("/admin/quota-pool/rebalance", headers=admin_headers)
    assert r.status_code == 200
    summary = r.json()
    assert summary["scanned"] == 1
    assert summary["changed"] == 1
    assert summary["T_before"] == 1000
    assert summary["algorithm_version"] == "v1"

    # Status should now show last_rebalance_at
    status_r = await app_client.get("/admin/quota-pool/status", headers=admin_headers)
    sbody = status_r.json()
    assert sbody["last_rebalance_at"] is not None
    assert sbody["pool_member_count"] == 1
    assert sbody["distributable"] == 1000

    # List endpoint
    list_r = await app_client.get(
        "/admin/quota-pool/rebalance-log", headers=admin_headers
    )
    assert len(list_r.json()) == 1

    # Detail endpoint with `details` field
    detail_r = await app_client.get(
        f"/admin/quota-pool/rebalance-log/{summary['id']}", headers=admin_headers
    )
    body = detail_r.json()
    assert "details" in body
    assert body["details"]["reserved_total"] == 0
    assert len(body["details"]["allocations"]) == 1
    assert body["details"]["allocations"][0]["after"] == 1000  # alone in pool

    # The allocation's quota was actually updated
    alloc_after = (
        await app_client.get(
            f"/admin/allocations?member_id={alloc['member_id']}",
            headers=admin_headers,
        )
    ).json()
    assert alloc_after[0]["quota_tokens_per_month"] == 1000
