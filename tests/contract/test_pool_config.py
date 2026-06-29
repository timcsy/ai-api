"""Phase 39 (053): admin-editable quota-pool config (T / floor) + suggestion.

T/floor move from env to a DB singleton; GET status lazy-seeds from env on first
read (no behaviour change), PUT persists + audits, validation enforces T ≥ floorxN.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog


async def _make_pool_allocation(
    client: AsyncClient, admin_headers: dict, subject: str, model: str = "azure/gpt-4o"
) -> None:
    """Active, non-service, non-locked allocation → counts as a pool member (N)."""
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": subject, "resource_model": model},
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_status_lazy_seeds_config_from_env(
    app_client: AsyncClient, admin_headers, monkeypatch
) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "0")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "1000")
    get_settings.cache_clear()
    body = (await app_client.get("/admin/quota-pool/status", headers=admin_headers)).json()
    assert body["config"]["total_tokens_per_month"] == 0  # seeded from env
    assert body["config"]["floor_per_allocation"] == 1000
    assert "suggestion" in body and "suggested_total" in body["suggestion"]
    assert body["total_T"] == body["config"]["total_tokens_per_month"]  # single source


@pytest.mark.asyncio
async def test_put_persists_and_status_reflects(
    app_client: AsyncClient, admin_headers, monkeypatch
) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "0")
    get_settings.cache_clear()
    await _make_pool_allocation(app_client, admin_headers, "alice@x.com")  # N=1

    r = await app_client.put(
        "/admin/quota-pool/config", headers=admin_headers,
        json={"total_tokens_per_month": 60000, "floor_per_allocation": 1000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["total_tokens_per_month"] == 60000

    body = (await app_client.get("/admin/quota-pool/status", headers=admin_headers)).json()
    assert body["config"]["total_tokens_per_month"] == 60000  # persisted, no redeploy
    assert body["total_T"] == 60000  # GET == what rebalance would use

    # Audited (FR-008).
    async with get_sessionmaker()() as s:
        rows = (await s.execute(
            select(AuthAuditLog).where(AuthAuditLog.event_type == AuditEventType.pool_config_updated)
        )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_put_rejects_total_below_floor_times_members(
    app_client: AsyncClient, admin_headers
) -> None:
    await _make_pool_allocation(app_client, admin_headers, "bob@x.com")  # N=1

    r = await app_client.put(
        "/admin/quota-pool/config", headers=admin_headers,
        json={"total_tokens_per_month": 500, "floor_per_allocation": 1000},  # 500 < 1000x1
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "invalid_pool_config"


@pytest.mark.asyncio
async def test_put_rejects_negative(app_client: AsyncClient, admin_headers) -> None:
    r = await app_client.put(
        "/admin/quota-pool/config", headers=admin_headers,
        json={"total_tokens_per_month": -1, "floor_per_allocation": 1000},
    )
    assert r.status_code == 422  # pydantic ge=0


@pytest.mark.asyncio
async def test_put_unauthorized(app_client: AsyncClient) -> None:
    r = await app_client.put(
        "/admin/quota-pool/config",
        json={"total_tokens_per_month": 1, "floor_per_allocation": 0},
    )
    assert r.status_code == 401
