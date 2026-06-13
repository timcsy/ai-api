"""Integration tests for Phase 3c quota pool: rebalance, exemption, rollback."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from ulid import ULID

from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import (
    Allocation,
    AllocationStatus,
    AuthAuditLog,
    CallOutcome,
    CallRecord,
    Credential,
    Member,
    MemberProvider,
    MemberStatus,
    RebalanceLog,
)
from ai_api.services.quota_pool import (
    PoolDisabledError,
    PoolExhaustedByReservedError,
    PoolIdleError,
    apply_rebalance,
)


def _last_month_anchor(now: datetime | None = None) -> datetime:
    n = now or datetime.now(UTC)
    if n.month == 1:
        return datetime(n.year - 1, 12, 15, tzinfo=UTC)
    return datetime(n.year, n.month - 1, 15, tzinfo=UTC)


async def _seed_member_and_allocation(
    *,
    email: str,
    usage: int,
    is_service: bool = False,
    quota_locked: bool = False,
    initial_quota: int | None = None,
) -> str:
    sm = get_sessionmaker()
    async with sm() as s:
        now = datetime.now(UTC)
        m = Member(
            id=str(ULID()),
            email=email,
            provider=MemberProvider.external,
            display_name=email,
            status=MemberStatus.active,
            password_hash=None,
            created_at=now,
            disabled_at=None,
            created_by="test",
        )
        s.add(m)
        await s.flush()
        a = Allocation(
            id=str(ULID()),
            member_id=m.id,
            subject_snapshot=email,
            resource_model="gpt-4o-mini",
            status=AllocationStatus.active,
            created_at=now,
            revoked_at=None,
            created_by="test",
            note=None,
            quota_tokens_per_month=initial_quota,
            is_service_allocation=is_service,
            quota_locked=quota_locked,
        )
        s.add(a)
        s.add(
            Credential(
                id=str(ULID()),
                name="預設",
                member_id=a.member_id,
                token_fingerprint=str(ULID()) + "xxxxxxxxxxxxxxxxxxxx",
                token_prefix="aiapi_xx",
                created_at=now,
            )
        )
        await s.flush()
        if usage > 0:
            ts = _last_month_anchor(now)
            s.add(
                CallRecord(
                    id=str(ULID()),
                    request_id="seed",
                    allocation_id=a.id,
                    subject=email,
                    model="gpt-4o-mini",
                    started_at=ts,
                    finished_at=ts,
                    status_code=200,
                    outcome=CallOutcome.success,
                    prompt_tokens=usage,
                    completion_tokens=0,
                    total_tokens=usage,
                )
            )
        await s.commit()
        return a.id


async def _quotas() -> dict[str, int | None]:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(Allocation.id, Allocation.quota_tokens_per_month))).all()
        return {r[0]: r[1] for r in rows}


async def _audit_event_types() -> list[str]:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(AuthAuditLog.event_type))).all()
        return [str(r[0]) for r in rows]


async def _rebalance_log_count() -> int:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(RebalanceLog))).all()
        return len(rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us1_general_5_3_2(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    a_id = await _seed_member_and_allocation(email="a@x.com", usage=50)
    b_id = await _seed_member_and_allocation(email="b@x.com", usage=30)
    c_id = await _seed_member_and_allocation(email="c@x.com", usage=20)

    sm = get_sessionmaker()
    async with sm() as s:
        outcome = await apply_rebalance(s, trigger="admin:test")
        await s.commit()
    assert outcome.log is not None

    quotas = await _quotas()
    assert quotas[a_id] == 450
    assert quotas[b_id] == 310
    assert quotas[c_id] == 240
    assert sum(v for v in quotas.values() if v) == 1000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us3_service_and_locked_exempt(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    alice = await _seed_member_and_allocation(
        email="alice@x.com", usage=0, is_service=True, initial_quota=500
    )
    bob = await _seed_member_and_allocation(
        email="bob@x.com", usage=0, quota_locked=True, initial_quota=200
    )
    carol = await _seed_member_and_allocation(email="carol@x.com", usage=10)

    sm = get_sessionmaker()
    async with sm() as s:
        outcome = await apply_rebalance(s, trigger="admin:test")
        await s.commit()
    assert outcome.log is not None

    q = await _quotas()
    assert q[alice] == 500  # unchanged
    assert q[bob] == 200  # unchanged
    assert q[carol] == 300  # T - 500 - 200 = 300


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us3_pool_exhausted(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "300")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    await _seed_member_and_allocation(
        email="big@x.com", usage=0, is_service=True, initial_quota=400
    )
    pool_id = await _seed_member_and_allocation(email="pool@x.com", usage=5)
    q_before = (await _quotas())[pool_id]

    sm = get_sessionmaker()
    async with sm() as s:
        with pytest.raises(PoolExhaustedByReservedError):
            await apply_rebalance(s, trigger="admin:test")
        await s.commit()  # commit so audit row persists

    # Pool member quota must not have changed
    q_after = (await _quotas())[pool_id]
    assert q_after == q_before
    # Audit shows failure
    assert "pool_exhausted_by_reserved" in await _audit_event_types()
    # No RebalanceLog row
    assert await _rebalance_log_count() == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us4_zero_usage_member_gets_only_floor(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    heavy = await _seed_member_and_allocation(email="heavy@x.com", usage=100)
    new = await _seed_member_and_allocation(email="new@x.com", usage=0)

    sm = get_sessionmaker()
    async with sm() as s:
        await apply_rebalance(s, trigger="admin:test")
        await s.commit()

    q = await _quotas()
    assert q[new] == 100  # floor only
    assert q[heavy] == 900  # 100 + (1000 - 200) * 1.0
    assert q[new] + q[heavy] == 1000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pool_disabled_raises(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "0")
    get_settings.cache_clear()
    sm = get_sessionmaker()
    async with sm() as s:
        with pytest.raises(PoolDisabledError):
            await apply_rebalance(s, trigger="admin:test")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pool_idle_raises(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    get_settings.cache_clear()
    # Only a service allocation exists
    await _seed_member_and_allocation(
        email="onlysvc@x.com", usage=0, is_service=True, initial_quota=500
    )
    sm = get_sessionmaker()
    async with sm() as s:
        with pytest.raises(PoolIdleError):
            await apply_rebalance(s, trigger="admin:test")
        await s.commit()
    assert "pool_idle" in await _audit_event_types()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cron_dedup_same_month(app_client, monkeypatch) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    await _seed_member_and_allocation(email="x@x.com", usage=10)

    sm = get_sessionmaker()
    async with sm() as s:
        outcome1 = await apply_rebalance(s, trigger="cron")
        await s.commit()
    assert outcome1.log is not None

    async with sm() as s:
        outcome2 = await apply_rebalance(s, trigger="cron")
        await s.commit()
    # Second cron-triggered run is deduped
    assert outcome2.log is None
    assert outcome2.skipped_reason == "cron_dedup_same_month"
    assert await _rebalance_log_count() == 1

    # Manual trigger after cron is still allowed
    async with sm() as s:
        outcome3 = await apply_rebalance(s, trigger="admin:test")
        await s.commit()
    assert outcome3.log is not None
    assert await _rebalance_log_count() == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us2_rollback_on_conservation_failure(
    app_client, monkeypatch
) -> None:
    """If compute_rebalance returns inconsistent sums, all updates roll back."""
    from unittest.mock import patch

    from ai_api.services.quota_pool import (
        RebalanceConservationError,
        RebalanceResult,
    )

    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    await _seed_member_and_allocation(email="a@x.com", usage=50, initial_quota=500)
    await _seed_member_and_allocation(email="b@x.com", usage=50, initial_quota=500)
    before = await _quotas()

    def _broken(*, T, floor, reserved_total, pool):
        # Return numbers that don't sum to T (intentional bug)
        return [
            RebalanceResult(allocation_id=m.allocation_id, new_quota=999, reason="ratio")
            for m in pool
        ]

    sm = get_sessionmaker()
    with patch("ai_api.services.quota_pool.compute_rebalance", _broken):
        async with sm() as s:
            with pytest.raises(RebalanceConservationError):
                await apply_rebalance(s, trigger="admin:test")
            # Inner _broken doesn't write audit; we still want NO RebalanceLog committed
            await s.rollback()

    after = await _quotas()
    assert after == before  # quota unchanged
    assert await _rebalance_log_count() == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_cap_untouched_by_rebalance(app_client, monkeypatch) -> None:
    """Phase 33 (046) SC-005: the adaptive pool only redistributes TOKEN quota; a
    cost cap is an independent hard cap and must not be rebalanced."""
    from decimal import Decimal

    from sqlalchemy import update as sa_update

    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    a_id = await _seed_member_and_allocation(email="ca@x.com", usage=50)
    await _seed_member_and_allocation(email="cb@x.com", usage=30)
    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(sa_update(Allocation).where(Allocation.id == a_id)
                        .values(quota_cost_usd_per_month=Decimal("7.50")))
        await s.commit()
    async with sm() as s:
        await apply_rebalance(s, trigger="admin:test")
        await s.commit()

    quotas = await _quotas()
    assert quotas[a_id] is not None and quotas[a_id] > 0  # token quota WAS rebalanced
    async with sm() as s:
        cap = (await s.execute(
            select(Allocation.quota_cost_usd_per_month).where(Allocation.id == a_id)
        )).scalar_one()
    assert cap == Decimal("7.50")  # cost cap UNCHANGED
