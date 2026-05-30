"""US4 integration tests: anomaly_detector behaviour under baseline + cold-start."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import (
    Allocation,
    AllocationStatus,
    CallOutcome,
    CallRecord,
    Credential,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.anomaly import detect_and_quarantine


async def _seed_member_and_alloc(*, is_service: bool = False) -> str:
    sm = get_sessionmaker()
    async with sm() as s:
        m = Member(
            id=str(ULID()),
            email="x@y.com",
            provider=MemberProvider.external,
            external_id=None,
            display_name="x",
            status=MemberStatus.active,
            password_hash=None,
            created_at=datetime.now(UTC),
            disabled_at=None,
            created_by="test",
        )
        s.add(m)
        await s.flush()
        a = Allocation(
            id=str(ULID()),
            member_id=m.id,
            subject_snapshot=m.email,
            resource_model="gpt-4o-mini",
            status=AllocationStatus.active,
            created_at=datetime.now(UTC) - timedelta(hours=48),
            revoked_at=None,
            created_by="test",
            note=None,
            is_service_allocation=is_service,
        )
        s.add(a)
        s.add(
            Credential(
                allocation_id=a.id,
                token_fingerprint="dummy" * 12 + "abcd",
                token_prefix="aiapi_xx",
                created_at=datetime.now(UTC),
            )
        )
        await s.commit()
        return a.id


async def _add_calls(alloc_id: str, count: int, hour_offset_from_now: int) -> None:
    sm = get_sessionmaker()
    # Spread `count` rows uniformly *within* the hour starting `hour_offset_from_now` ago.
    # Use seconds-back-from-now so they all sit before "now".
    base = datetime.now(UTC) - timedelta(hours=hour_offset_from_now)
    async with sm() as s:
        for i in range(count):
            ts = base - timedelta(seconds=i % 3500)  # stay inside the hour
            s.add(
                CallRecord(
                    id=str(ULID()),
                    request_id=f"r-{ULID()}",
                    allocation_id=alloc_id,
                    subject="x@y.com",
                    model="gpt-4o-mini",
                    started_at=ts,
                    finished_at=ts,
                    status_code=200,
                    outcome=CallOutcome.success,
                    prompt_tokens=10,
                    completion_tokens=10,
                    total_tokens=20,
                )
            )
        await s.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_baseline_then_spike_triggers_quarantine(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    # Baseline: 100 calls / hour over the past 23 hours = 2300 calls
    for h in range(2, 25):  # hours 2..24 ago (i.e. NOT in the last hour)
        await _add_calls(alloc_id, 100, h)
    # Recent burst: 1100 calls in the last hour (≥ 10x baseline 100/hr)
    await _add_calls(alloc_id, 1100, 0)

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert len(decisions) == 1
    sm = get_sessionmaker()
    async with sm() as s:
        alloc = (
            await s.execute(select(Allocation).where(Allocation.id == alloc_id))
        ).scalar_one()
        assert alloc.status == AllocationStatus.quarantined


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cold_start_under_absolute_does_not_trigger(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    # No baseline; 500 recent calls (< absolute_cold_start=10000) → should NOT quarantine
    await _add_calls(alloc_id, 500, 0)

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert decisions == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cold_start_over_absolute_triggers(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    # No baseline; 10001 calls (≥ absolute_cold_start) → trigger
    await _add_calls(alloc_id, 10001, 0)

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert len(decisions) == 1
    assert decisions[0].reason == "absolute_cold_start"


# Phase 11 follow-up — service allocations (e.g. Codex/agent CLIs) are exempt;
# their traffic is bursty by design and should not be auto-quarantined.
@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_allocation_is_exempt_from_quarantine(app_client) -> None:
    alloc_id = await _seed_member_and_alloc(is_service=True)
    # Same shape that would normally trigger 'ratio': baseline + spike.
    for h in range(2, 25):
        await _add_calls(alloc_id, 100, h)
    await _add_calls(alloc_id, 1100, 0)

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert decisions == []
    async with sm() as s:
        alloc = (
            await s.execute(select(Allocation).where(Allocation.id == alloc_id))
        ).scalar_one()
        assert alloc.status == AllocationStatus.active
