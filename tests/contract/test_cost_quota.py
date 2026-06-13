"""Phase 33 (046) US1: cost-based monthly quota — per-allocation USD spend cap.

Cost quota is checked in preflight BEFORE credential resolution, so the *blocked*
paths need no upstream mock. Cost accrual is seeded directly as CallRecords (a real
priced call would just be a slower way to reach the same cost sum).
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import Allocation, CallOutcome, CallRecord

MODEL = "azure/gpt-test"


async def _alloc(client: AsyncClient, admin: dict, model: str = MODEL) -> dict:
    r = await client.post("/admin/allocations", headers=admin,
                          json={"subject": "alice@example.com", "resource_model": model})
    assert r.status_code == 201, r.text
    return r.json()


async def _set_caps(alloc_id: str, *, cost: str | None = None, tokens: int | None = None) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        vals: dict = {}
        if cost is not None:
            vals["quota_cost_usd_per_month"] = Decimal(cost)
        if tokens is not None:
            vals["quota_tokens_per_month"] = tokens
        await s.execute(update(Allocation).where(Allocation.id == alloc_id).values(**vals))
        await s.commit()


async def _seed_call(alloc_id: str, *, cost: str | None, tokens: int | None = None,
                     unit: str | None = None, quantity: int | None = None) -> None:
    now = datetime.now(UTC)
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(CallRecord(
            id=str(ULID()), request_id="seed", allocation_id=alloc_id, subject="alice@example.com",
            model=MODEL, started_at=now, finished_at=now, status_code=200,
            outcome=CallOutcome.success,
            total_tokens=tokens, quantity=quantity, unit=unit,
            cost_usd=Decimal(cost) if cost is not None else None,
        ))
        await s.commit()


async def _chat(client: AsyncClient, token: str, model: str = MODEL):
    return await client.post(
        "/v1/chat/completions", headers={"Authorization": f"Bearer {token}"},
        json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
    )


async def _last(outcome: CallOutcome) -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == outcome)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


# --- T006: cost cap blocks across token + non-token endpoints ----------------
@pytest.mark.asyncio
async def test_cost_cap_blocks_mixed_endpoints(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _set_caps(alloc["id"], cost="1.00")
    # token call $0.60 + OCR page call $0.40 →累計 $1.00 = cap
    await _seed_call(alloc["id"], cost="0.60", tokens=300)
    await _seed_call(alloc["id"], cost="0.40", unit="page", quantity=2)
    r = await _chat(app_client, alloc["token"])
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "cost_quota_exceeded"
    rec = await _last(CallOutcome.rejected_cost_quota_exceeded)
    assert rec is not None and rec.allocation_id == alloc["id"]


# --- T007: no cost cap → cost gate doesn't fire; token path intact -----------
@pytest.mark.asyncio
async def test_no_cost_cap_gate_does_not_fire(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)  # no cost cap set
    await _seed_call(alloc["id"], cost="999.00", unit="page", quantity=9)  # huge non-token spend
    r = await _chat(app_client, alloc["token"])
    # gate must NOT block on cost (it has no cost cap); it fails later (no upstream),
    # but never with cost_quota_exceeded.
    if r.status_code == 403:
        assert r.json()["error"]["code"] != "cost_quota_exceeded"


@pytest.mark.asyncio
async def test_token_cap_still_blocks_zero_regression(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _set_caps(alloc["id"], tokens=100)          # token cap, NO cost cap
    await _seed_call(alloc["id"], cost=None, tokens=100)  # token usage at cap
    r = await _chat(app_client, alloc["token"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "quota_exceeded"


# --- T008: both caps → either one trips ------------------------------------
@pytest.mark.asyncio
async def test_both_caps_cost_trips(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _set_caps(alloc["id"], cost="1.00", tokens=1_000_000)  # token slack, cost tight
    await _seed_call(alloc["id"], cost="1.00", unit="minute", quantity=59)
    r = await _chat(app_client, alloc["token"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "cost_quota_exceeded"


@pytest.mark.asyncio
async def test_both_caps_token_trips(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _set_caps(alloc["id"], cost="100.00", tokens=10)  # cost slack, token tight
    await _seed_call(alloc["id"], cost="0.01", tokens=10)
    r = await _chat(app_client, alloc["token"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "quota_exceeded"


# --- T009: unpriced calls don't accrue, don't block ------------------------
@pytest.mark.asyncio
async def test_unpriced_calls_not_counted(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _set_caps(alloc["id"], cost="1.00")
    # many unpriced (cost_usd NULL) calls → sum stays 0 → not blocked by cost cap
    for _ in range(5):
        await _seed_call(alloc["id"], cost=None, unit="page", quantity=10)
    r = await _chat(app_client, alloc["token"])
    if r.status_code == 403:
        assert r.json()["error"]["code"] != "cost_quota_exceeded"


# --- SC-006: current_month_cost = sum(cost_usd), unpriced as 0 -------------
@pytest.mark.asyncio
async def test_current_month_cost_sums_all_units(app_client: AsyncClient, admin_headers):
    from ai_api.services.quota import current_month_cost

    alloc = await _alloc(app_client, admin_headers)
    await _seed_call(alloc["id"], cost="0.60", tokens=300)       # token
    await _seed_call(alloc["id"], cost="0.40", unit="page", quantity=2)  # non-token
    await _seed_call(alloc["id"], cost=None, unit="page", quantity=1)    # unpriced → 0
    sm = get_sessionmaker()
    async with sm() as s:
        total = await current_month_cost(s, alloc["id"])
    assert total == Decimal("1.00")


# --- T012: admin API round-trips the cost cap ------------------------------
@pytest.mark.asyncio
async def test_admin_api_sets_and_returns_cost_cap(app_client: AsyncClient, admin_headers):
    r = await app_client.post("/admin/allocations", headers=admin_headers, json={
        "subject": "bob@example.com", "resource_model": MODEL,
        "quota_cost_usd_per_month": "5.00",
    })
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["quota_cost_usd_per_month"]) == Decimal("5.00")
