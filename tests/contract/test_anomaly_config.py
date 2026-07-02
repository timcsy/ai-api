"""Spec 054: admin anomaly-detector config (switch / pause / thresholds).

Thresholds + switch move to a DB singleton; GET lazy-seeds from env on first read
(no behaviour change), PUT persists + audits, validation enforces bounds.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog


@pytest.mark.asyncio
async def test_get_lazy_seeds_defaults(app_client: AsyncClient, admin_headers) -> None:
    body = (await app_client.get("/admin/anomaly/config", headers=admin_headers)).json()
    assert body["auto_quarantine_enabled"] is True
    assert body["status"] == "enabled"
    assert body["effective_enforcing"] is True
    assert body["thresholds"]["threshold_multiplier"] == 10.0
    assert body["thresholds"]["baseline_min_calls"] == 200


@pytest.mark.asyncio
async def test_disable_switch_persists_and_audits(app_client: AsyncClient, admin_headers) -> None:
    r = await app_client.put(
        "/admin/anomaly/config", headers=admin_headers,
        json={"auto_quarantine_enabled": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "disabled"
    assert r.json()["effective_enforcing"] is False

    body = (await app_client.get("/admin/anomaly/config", headers=admin_headers)).json()
    assert body["auto_quarantine_enabled"] is False

    async with get_sessionmaker()() as s:
        rows = (await s.execute(
            select(AuthAuditLog).where(
                AuthAuditLog.event_type == AuditEventType.anomaly_config_updated
            )
        )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_pause_until_future_is_paused(app_client: AsyncClient, admin_headers) -> None:
    r = await app_client.put(
        "/admin/anomaly/config", headers=admin_headers,
        json={"pause_until": "2999-01-01T00:00:00Z"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"
    assert r.json()["effective_enforcing"] is False


@pytest.mark.asyncio
async def test_thresholds_update_and_validation(app_client: AsyncClient, admin_headers) -> None:
    ok = await app_client.put(
        "/admin/anomaly/config", headers=admin_headers,
        json={"threshold_multiplier": 25, "min_calls": 300, "baseline_min_calls": 500},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["thresholds"]["threshold_multiplier"] == 25.0
    assert ok.json()["thresholds"]["min_calls"] == 300

    bad = await app_client.put(
        "/admin/anomaly/config", headers=admin_headers,
        json={"threshold_multiplier": 0.5},  # < 1
    )
    assert bad.status_code == 422

    neg = await app_client.put(
        "/admin/anomaly/config", headers=admin_headers,
        json={"min_calls": -1},
    )
    assert neg.status_code == 422


@pytest.mark.asyncio
async def test_unauthorized(app_client: AsyncClient) -> None:
    assert (await app_client.get("/admin/anomaly/config")).status_code == 401
    assert (await app_client.put("/admin/anomaly/config", json={})).status_code == 401
