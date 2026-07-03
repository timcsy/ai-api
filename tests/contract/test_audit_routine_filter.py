"""Audit log hides high-frequency routine system events (anomaly_detector_run)
by default; a flag / explicit event_type filter reveals them."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from ai_api.auth import audit
from ai_api.db import get_sessionmaker
from ai_api.models import ActorType, AuditEventType


async def _seed() -> None:
    async with get_sessionmaker()() as s:
        await audit.record(
            s, event_type=AuditEventType.anomaly_detector_run, actor_type=ActorType.system
        )
        await audit.record(
            s, event_type=AuditEventType.login_success, actor_type=ActorType.member, actor_id="m1"
        )
        await s.commit()


@pytest.mark.asyncio
async def test_routine_hidden_by_default(app_client: AsyncClient, admin_headers) -> None:
    await _seed()
    rows = (await app_client.get("/admin/audit", headers=admin_headers)).json()["rows"]
    types = {r["event_type"] for r in rows}
    assert "anomaly_detector_run" not in types
    assert "login_success" in types


@pytest.mark.asyncio
async def test_routine_shown_with_include_flag(app_client: AsyncClient, admin_headers) -> None:
    await _seed()
    rows = (
        await app_client.get("/admin/audit?include_routine=true", headers=admin_headers)
    ).json()["rows"]
    assert "anomaly_detector_run" in {r["event_type"] for r in rows}


@pytest.mark.asyncio
async def test_explicit_event_type_overrides_hiding(app_client: AsyncClient, admin_headers) -> None:
    await _seed()
    rows = (
        await app_client.get(
            "/admin/audit?event_type=anomaly_detector_run", headers=admin_headers
        )
    ).json()["rows"]
    assert len(rows) >= 1
    assert all(r["event_type"] == "anomaly_detector_run" for r in rows)
