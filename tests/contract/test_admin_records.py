"""Spec 056: admin per-call records viewer (GET /admin/records) — filters, cursor,
per-record cost, authorization."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome
from ai_api.services.records import RecordsService


async def _member_and_alloc(client: AsyncClient, admin_headers: dict, email: str) -> tuple[str, str]:
    m = (await client.post("/admin/members", headers=admin_headers, json={
        "email": email, "provider": "local_password", "initial_password": "VerySafePass123",
        "send_invitation": False,
    })).json()
    a = (await client.post("/admin/allocations", headers=admin_headers, json={
        "member_id": m["id"], "resource_model": "azure/gpt-4o",
    })).json()
    return m["id"], a["id"]


async def _seed(alloc_id: str, subject: str) -> None:
    now = datetime.now(UTC)
    async with get_sessionmaker()() as s:
        svc = RecordsService(s)
        await svc.record_call(
            request_id="r1", allocation_id=alloc_id, subject=subject, model="azure/gpt-4o",
            started_at=now - timedelta(minutes=2), status_code=200, outcome=CallOutcome.success,
            total_tokens=100, cost_usd=Decimal("0.0500"),
        )
        await svc.record_call(  # unpriced failure
            request_id="r2", allocation_id=alloc_id, subject=subject, model="azure/gpt-4o",
            started_at=now - timedelta(minutes=1), status_code=502,
            outcome=CallOutcome.upstream_error, error_message="boom",
        )
        await s.commit()


@pytest.mark.asyncio
async def test_admin_records_by_member_with_cost(app_client: AsyncClient, admin_headers) -> None:
    mid, aid = await _member_and_alloc(app_client, admin_headers, "rec1@x.com")
    await _seed(aid, "rec1@x.com")
    body = (await app_client.get(f"/admin/records?member_id={mid}", headers=admin_headers)).json()
    assert len(body["items"]) == 2
    priced = next(i for i in body["items"] if i["request_id"] == "r1")
    assert priced["cost_usd"] == "0.050000" or Decimal(priced["cost_usd"]) == Decimal("0.05")
    unpriced = next(i for i in body["items"] if i["request_id"] == "r2")
    assert unpriced["cost_usd"] is None  # unpriced ⇒ null, not 0


@pytest.mark.asyncio
async def test_admin_records_outcome_filter(app_client: AsyncClient, admin_headers) -> None:
    _, aid = await _member_and_alloc(app_client, admin_headers, "rec2@x.com")
    await _seed(aid, "rec2@x.com")
    body = (await app_client.get(
        f"/admin/records?allocation_id={aid}&outcome=success", headers=admin_headers
    )).json()
    assert all(i["outcome"] == "success" for i in body["items"])
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_admin_records_cursor(app_client: AsyncClient, admin_headers) -> None:
    _, aid = await _member_and_alloc(app_client, admin_headers, "rec3@x.com")
    await _seed(aid, "rec3@x.com")
    p1 = (await app_client.get(f"/admin/records?allocation_id={aid}&limit=1", headers=admin_headers)).json()
    assert len(p1["items"]) == 1 and p1["next_before"]
    p2 = (await app_client.get(
        f"/admin/records?allocation_id={aid}&limit=1&before={p1['next_before']}", headers=admin_headers
    )).json()
    assert len(p2["items"]) == 1
    assert p1["items"][0]["id"] != p2["items"][0]["id"]  # no overlap


@pytest.mark.asyncio
async def test_admin_records_unauthorized(app_client: AsyncClient) -> None:
    assert (await app_client.get("/admin/records")).status_code == 401
