"""Spec 056: member's own per-call list (/me/allocations/{id}/calls) includes cost."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome
from ai_api.services.records import RecordsService


@pytest.mark.asyncio
async def test_me_calls_include_cost(app_client: AsyncClient, admin_headers) -> None:
    m = (await app_client.post("/admin/members", headers=admin_headers, json={
        "email": "mine@x.com", "provider": "local_password",
        "initial_password": "VerySafePass123", "send_invitation": False,
    })).json()
    a = (await app_client.post("/admin/allocations", headers=admin_headers, json={
        "member_id": m["id"], "resource_model": "azure/gpt-4o",
    })).json()
    async with get_sessionmaker()() as s:
        await RecordsService(s).record_call(
            request_id="rc", allocation_id=a["id"], subject="mine@x.com", model="azure/gpt-4o",
            started_at=datetime.now(UTC), status_code=200, outcome=CallOutcome.success,
            total_tokens=50, cost_usd=Decimal("0.0200"),
        )
        await s.commit()

    await app_client.post("/auth/local/login", json={"email": "mine@x.com", "password": "VerySafePass123"})
    body = (await app_client.get(f"/me/allocations/{a['id']}/calls")).json()
    assert len(body["items"]) == 1
    rec = body["items"][0]
    assert Decimal(rec["cost_usd"]) == Decimal("0.02")
    assert "unit" in rec and "quantity" in rec
