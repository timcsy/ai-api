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
                id=str(ULID()),
                name="預設",
                member_id=a.member_id,
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


# Spec 054 — US2: sparse baseline must fall back to the absolute threshold, so a
# legit spike on a freshly-migrated / new / workshop allocation is NOT false-flagged.
@pytest.mark.integration
@pytest.mark.asyncio
async def test_sparse_baseline_spike_does_not_trigger(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    # Sparse baseline: 84 calls over 23h (< baseline_min_calls=200) → ratio DISTRUSTED.
    for h in range(2, 25):
        await _add_calls(alloc_id, 4, h)  # ~92 total, well under 200
    # Workshop-style spike: 103 calls (would trip ratio 10x of ~4/hr, but < absolute).
    await _add_calls(alloc_id, 103, 0)

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert decisions == []  # sparse baseline → absolute only → 103 < 10000 → no quarantine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sparse_baseline_over_absolute_still_triggers(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    for h in range(2, 25):
        await _add_calls(alloc_id, 4, h)
    await _add_calls(alloc_id, 10001, 0)  # genuinely runaway → still caught

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert len(decisions) == 1


# Spec 054 — US1: admin can disable/pause auto-quarantine; the detector still scans
# but must not quarantine anyone.
async def _set_anomaly_config(**kwargs) -> None:
    from ai_api.services.anomaly import get_anomaly_config

    sm = get_sessionmaker()
    async with sm() as s:
        cfg = await get_anomaly_config(s)
        for k, v in kwargs.items():
            setattr(cfg, k, v)
        await s.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disabled_switch_skips_quarantine(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    for h in range(2, 25):
        await _add_calls(alloc_id, 100, h)  # robust baseline
    await _add_calls(alloc_id, 1100, 0)  # would normally quarantine (ratio)
    await _set_anomaly_config(auto_quarantine_enabled=False)

    sm = get_sessionmaker()
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert decisions == []  # enforcement off → scanned but not quarantined
    async with sm() as s:
        alloc = (
            await s.execute(select(Allocation).where(Allocation.id == alloc_id))
        ).scalar_one()
        assert alloc.status == AllocationStatus.active


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paused_until_future_skips_then_resumes(app_client) -> None:
    alloc_id = await _seed_member_and_alloc()
    for h in range(2, 25):
        await _add_calls(alloc_id, 100, h)
    await _add_calls(alloc_id, 1100, 0)
    # Paused far in the future → skipped.
    await _set_anomaly_config(pause_until=datetime(2999, 1, 1, tzinfo=UTC))
    sm = get_sessionmaker()
    async with sm() as s:
        assert await detect_and_quarantine(s) == []
        await s.commit()
    # Pause expired (past) → enforcement resumes automatically.
    await _set_anomaly_config(pause_until=datetime(2000, 1, 1, tzinfo=UTC))
    async with sm() as s:
        decisions = await detect_and_quarantine(s)
        await s.commit()
    assert len(decisions) == 1


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
