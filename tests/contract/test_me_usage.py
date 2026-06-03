"""Phase 018 US1/US2: GET /me/usage member-scoped usage overview.

Contract: specs/018-member-usage-overview/contracts/me-usage.md
Docker-free — uses the contract app_client (in-memory SQLite).
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import (
    Allocation,
    AllocationOrigin,
    AllocationStatus,
    CallOutcome,
    CallRecord,
)

NOW = datetime.now(UTC)


async def _login(client: AsyncClient, admin_headers: dict[str, str], email: str) -> str:
    """Create a local_password member + log in. Returns member id."""
    r = await client.post(
        "/admin/members",
        headers=admin_headers,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    member_id = r.json()["id"]
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return member_id


async def _seed_calls(member_id: str, model: str, calls: list[tuple[int, float | None]]) -> None:
    """Insert an allocation for member + success CallRecords (total_tokens, cost_usd)."""
    sm = get_sessionmaker()
    async with sm() as s:
        alloc_id = str(ULID())
        s.add(Allocation(
            id=alloc_id, member_id=member_id, subject_snapshot=model,
            resource_model=model, status=AllocationStatus.active, created_at=NOW,
            revoked_at=None, created_by="test", note=None, quota_tokens_per_month=None,
            is_service_allocation=False, quota_locked=False, origin=AllocationOrigin.admin,
        ))
        for total, cost in calls:
            s.add(CallRecord(
                id=str(ULID()), request_id=str(ULID()), allocation_id=alloc_id,
                subject=model, model=model, started_at=NOW, finished_at=NOW,
                status_code=200, outcome=CallOutcome.success,
                prompt_tokens=total // 2, completion_tokens=total - total // 2,
                total_tokens=total, cost_usd=cost, error_message=None,
            ))
        await s.commit()


# T007 — summary equals sum of member's successful calls
@pytest.mark.asyncio
async def test_me_usage_summary(app_client: AsyncClient, admin_headers) -> None:
    mid = await _login(app_client, admin_headers, "u1@x.com")
    await _seed_calls(mid, "azure/m", [(100, 1.0), (50, 0.5)])
    r = await app_client.get("/me/usage")
    assert r.status_code == 200
    body = r.json()
    s = body["summary"]
    assert s["total_tokens"] == 150
    assert s["call_count"] == 2
    assert float(s["total_cost_usd"]) == pytest.approx(1.5)
    assert s["has_unpriced"] is False


# Phase 11 — summary surfaces reasoning/cached token breakdown
@pytest.mark.asyncio
async def test_me_usage_summary_includes_reasoning_cached(
    app_client: AsyncClient, admin_headers
) -> None:
    mid = await _login(app_client, admin_headers, "rc@x.com")
    sm = get_sessionmaker()
    async with sm() as s:
        alloc_id = str(ULID())
        s.add(Allocation(
            id=alloc_id, member_id=mid, subject_snapshot="azure/gpt-5",
            resource_model="azure/gpt-5", status=AllocationStatus.active, created_at=NOW,
            revoked_at=None, created_by="test", note=None, quota_tokens_per_month=None,
            is_service_allocation=False, quota_locked=False, origin=AllocationOrigin.admin,
        ))
        s.add(CallRecord(
            id=str(ULID()), request_id=str(ULID()), allocation_id=alloc_id,
            subject="azure/gpt-5", model="azure/gpt-5", started_at=NOW, finished_at=NOW,
            status_code=200, outcome=CallOutcome.success,
            prompt_tokens=100, completion_tokens=200, total_tokens=300,
            reasoning_tokens=60, cached_tokens=40, cost_usd=None, error_message=None,
        ))
        await s.commit()
    r = await app_client.get("/me/usage")
    assert r.status_code == 200
    summ = r.json()["summary"]
    assert summ["reasoning_tokens"] == 60
    assert summ["cached_tokens"] == 40


@pytest.mark.asyncio
async def test_me_usage_empty_is_zero(app_client: AsyncClient, admin_headers) -> None:
    await _login(app_client, admin_headers, "empty@x.com")
    r = await app_client.get("/me/usage")
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["total_tokens"] == 0 and s["call_count"] == 0
    assert s["has_unpriced"] is False


# T008 — strict isolation: A never sees B
@pytest.mark.asyncio
async def test_me_usage_isolation(app_client: AsyncClient, admin_headers) -> None:
    a = await _login(app_client, admin_headers, "a@x.com")
    b = await _login(app_client, admin_headers, "b@x.com")  # logs in as B last
    await _seed_calls(a, "azure/m", [(100, 1.0)])
    await _seed_calls(b, "azure/m", [(999, 9.0)])
    # session is currently B → must see only B's 999
    r_b = await app_client.get("/me/usage")
    assert r_b.json()["summary"]["total_tokens"] == 999
    # switch to A → only 100
    await app_client.post("/auth/local/login", json={"email": "a@x.com", "password": "VerySafePass123"})
    r_a = await app_client.get("/me/usage")
    assert r_a.json()["summary"]["total_tokens"] == 100


# T009 — unauthenticated → 401
@pytest.mark.asyncio
async def test_me_usage_requires_session(app_client: AsyncClient) -> None:
    r = await app_client.get("/me/usage")
    assert r.status_code == 401


# T010 — has_unpriced flag
@pytest.mark.asyncio
async def test_me_usage_has_unpriced(app_client: AsyncClient, admin_headers) -> None:
    mid = await _login(app_client, admin_headers, "up@x.com")
    await _seed_calls(mid, "azure/m", [(100, 1.0), (200, None)])  # one call had no price
    r = await app_client.get("/me/usage")
    assert r.json()["summary"]["has_unpriced"] is True


# T016/T017 — breakdown sums to summary; group_by=member rejected
@pytest.mark.asyncio
async def test_me_usage_breakdown_by_model(app_client: AsyncClient, admin_headers) -> None:
    mid = await _login(app_client, admin_headers, "bd@x.com")
    await _seed_calls(mid, "azure/m1", [(100, 1.0)])
    await _seed_calls(mid, "azure/m2", [(200, 2.0)])
    r = await app_client.get("/me/usage?group_by=model")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total_tokens"] == 300
    breakdown = {b["group_key"]: b["total_tokens"] for b in body["breakdown"]}
    assert breakdown == {"azure/m1": 100, "azure/m2": 200}
    assert sum(breakdown.values()) == body["summary"]["total_tokens"]


@pytest.mark.asyncio
async def test_me_usage_group_by_member_rejected(app_client: AsyncClient, admin_headers) -> None:
    await _login(app_client, admin_headers, "gb@x.com")
    r = await app_client.get("/me/usage?group_by=member")
    assert r.status_code == 422


# T018 — time range recalculates (use params= so httpx URL-encodes the +00:00)
@pytest.mark.asyncio
async def test_me_usage_range_filters(app_client: AsyncClient, admin_headers) -> None:
    from datetime import timedelta

    mid = await _login(app_client, admin_headers, "range@x.com")
    await _seed_calls(mid, "azure/m", [(100, 1.0)])  # call at NOW
    # a window entirely in the past excludes the NOW call
    past_from = (NOW - timedelta(days=10)).isoformat()
    past_to = (NOW - timedelta(days=5)).isoformat()
    r = await app_client.get("/me/usage", params={"from": past_from, "to": past_to})
    assert r.status_code == 200
    assert r.json()["summary"]["total_tokens"] == 0
    # a window covering NOW includes it
    r2 = await app_client.get(
        "/me/usage",
        params={"from": (NOW - timedelta(days=1)).isoformat(),
                "to": (NOW + timedelta(days=1)).isoformat()},
    )
    assert r2.json()["summary"]["total_tokens"] == 100


# ===== Phase 17: GET /me/usage/timeseries (member-scoped daily charts) =====

async def _seed_alloc_with_calls_at(
    member_id: str, model: str, calls: list[tuple[datetime, int, float]]
) -> None:
    """One allocation for member + success CallRecords at given timestamps."""
    sm = get_sessionmaker()
    async with sm() as s:
        alloc_id = str(ULID())
        s.add(Allocation(
            id=alloc_id, member_id=member_id, subject_snapshot=model,
            resource_model=model, status=AllocationStatus.active, created_at=NOW,
            revoked_at=None, created_by="test", note=None, quota_tokens_per_month=None,
            is_service_allocation=False, quota_locked=False, origin=AllocationOrigin.admin,
        ))
        for when, total, cost in calls:
            s.add(CallRecord(
                id=str(ULID()), request_id=str(ULID()), allocation_id=alloc_id,
                subject=model, model=model, started_at=when, finished_at=when,
                status_code=200, outcome=CallOutcome.success,
                prompt_tokens=total // 2, completion_tokens=total - total // 2,
                total_tokens=total, cost_usd=cost, error_message=None,
            ))
        await s.commit()


# T002 — daily timeseries sums the member's OWN allocations per day
@pytest.mark.asyncio
async def test_my_timeseries_sums_own_allocations(app_client: AsyncClient, admin_headers) -> None:
    mid = await _login(app_client, admin_headers, "ts1@x.com")
    day1 = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
    day2 = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
    # two separate allocations, both contribute to day1
    await _seed_alloc_with_calls_at(mid, "azure/m1", [(day1, 1000, 0.10)])
    await _seed_alloc_with_calls_at(mid, "azure/m2", [(day1, 500, 0.05), (day2, 300, 0.03)])
    r = await app_client.get(
        "/me/usage/timeseries",
        params={"from": "2026-05-01T00:00:00+00:00", "to": "2026-05-31T00:00:00+00:00"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bucket"] == "day"
    points = {p["ts"][:10]: p for p in body["points"]}
    assert points["2026-05-10"]["tokens"] == 1500  # both allocations summed
    assert points["2026-05-10"]["call_count"] == 2
    assert points["2026-05-11"]["tokens"] == 300


# T003 — unauthenticated + invalid range
@pytest.mark.asyncio
async def test_my_timeseries_unauthenticated_401(app_client: AsyncClient) -> None:
    r = await app_client.get(
        "/me/usage/timeseries",
        params={"from": "2026-05-01T00:00:00+00:00", "to": "2026-05-31T00:00:00+00:00"},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_my_timeseries_invalid_range_400(app_client: AsyncClient, admin_headers) -> None:
    await _login(app_client, admin_headers, "ts-bad@x.com")
    r = await app_client.get(
        "/me/usage/timeseries",
        params={"from": "2026-05-31T00:00:00+00:00", "to": "2026-05-01T00:00:00+00:00"},
    )
    assert r.status_code == 400
