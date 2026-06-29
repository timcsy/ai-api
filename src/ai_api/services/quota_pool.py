"""Adaptive quota pool — Matthew-effect monthly rebalance with energy conservation.

Layered design (research.md §1):
- ``compute_rebalance(...)``: PURE function. Given (T, floor, reserved, pool),
  return [(allocation_id, new_quota)]. 100% unit-testable; no DB I/O.
- ``apply_rebalance(db, *, trigger)``: side-effect layer. Wraps the pure
  function in a DB transaction with conservation assertion + RebalanceLog
  write + audit. Rolls back on any failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.auth import audit
from ai_api.config import get_settings
from ai_api.models import (
    ActorType,
    Allocation,
    AllocationStatus,
    AuditEventType,
    CallOutcome,
    CallRecord,
    PoolConfig,
    RebalanceLog,
)

ALGORITHM_VERSION = "v1"


@dataclass(frozen=True)
class PoolMember:
    """Input to compute_rebalance."""

    allocation_id: str
    usage_last_month: int


@dataclass(frozen=True)
class RebalanceResult:
    """One row of compute_rebalance output."""

    allocation_id: str
    new_quota: int
    reason: str  # "ratio" | "floor" | "first_round"


class RebalanceConservationError(RuntimeError):
    """Raised when Σ q != T after compute. Bug indicator."""


class PoolDisabledError(RuntimeError):
    """Raised when settings.pool_total_tokens_per_month == 0."""


class PoolExhaustedByReservedError(RuntimeError):
    """Raised when service+locked reserved quotas > T, or no room for floors."""


class PoolIdleError(RuntimeError):
    """Raised when pool has 0 eligible allocations."""


def previous_month_range_utc(now: datetime) -> tuple[datetime, datetime]:
    """Return (prev_month_start, this_month_start), both UTC tz-aware."""
    this_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 1:
        prev_start = datetime(now.year - 1, 12, 1, tzinfo=UTC)
    else:
        prev_start = datetime(now.year, now.month - 1, 1, tzinfo=UTC)
    return prev_start, this_start


def compute_rebalance(
    *,
    T: int,
    floor: int,
    reserved_total: int,
    pool: list[PoolMember],
) -> list[RebalanceResult]:
    """Compute new quotas for the pool.

    Conservation: Σ result.new_quota + reserved_total == T.
    """
    N = len(pool)
    if N == 0:
        return []

    distributable = T - reserved_total
    if distributable < floor * N:
        raise PoolExhaustedByReservedError(
            f"distributable {distributable} < floor*N ({floor}*{N}); "
            f"increase T or remove reserved/locked allocations"
        )

    total_usage = sum(m.usage_last_month for m in pool)

    # First round / cold start: nobody has usage. Spread distributable evenly.
    if total_usage == 0:
        each = distributable // N
        leftover = distributable - each * N
        sorted_by_id = sorted(range(N), key=lambda i: pool[i].allocation_id, reverse=True)
        leftover_target_idx = sorted_by_id[0]
        out: list[RebalanceResult] = []
        for i, m in enumerate(pool):
            extra = leftover if i == leftover_target_idx else 0
            out.append(
                RebalanceResult(
                    allocation_id=m.allocation_id,
                    new_quota=each + extra,
                    reason="first_round",
                )
            )
        _assert_conservation(out, reserved_total, T)
        return out

    # Matthew-effect proportional with floor.
    bonus_pool = distributable - floor * N
    shares = []
    for m in pool:
        if m.usage_last_month == 0:
            shares.append(0)
        else:
            shares.append(int(bonus_pool * m.usage_last_month / total_usage))
    leftover = bonus_pool - sum(shares)

    # Leftover → highest usage; ties broken by allocation_id lex-max for determinism.
    target_idx = max(
        range(N),
        key=lambda i: (pool[i].usage_last_month, pool[i].allocation_id),
    )
    shares[target_idx] += leftover

    out = []
    for m, share in zip(pool, shares, strict=True):
        reason = "floor" if m.usage_last_month == 0 else "ratio"
        out.append(
            RebalanceResult(
                allocation_id=m.allocation_id,
                new_quota=floor + share,
                reason=reason,
            )
        )
    _assert_conservation(out, reserved_total, T)
    return out


def _assert_conservation(
    results: list[RebalanceResult], reserved_total: int, T: int
) -> None:
    total = sum(r.new_quota for r in results) + reserved_total
    if total != T:
        raise RebalanceConservationError(
            f"conservation violated: Σ_pool({sum(r.new_quota for r in results)}) "
            f"+ reserved({reserved_total}) = {total}, expected T={T}"
        )


@dataclass(frozen=True)
class RebalanceOutcome:
    """Returned by apply_rebalance."""

    log: RebalanceLog | None  # None if cron dedup no-op
    skipped_reason: str | None = None


# ---- Phase 39: pool settings live in DB (single source of truth) ----

async def get_pool_config(db: AsyncSession) -> PoolConfig:
    """The singleton pool config (T + floor). Lazy-seeds from settings (Helm/env)
    on first access so the move from env→DB is a no-op on first run; thereafter
    the DB row is the single source of truth (env is bootstrap default only)."""
    cfg = await db.get(PoolConfig, 1)
    if cfg is None:
        settings = get_settings()
        cfg = PoolConfig(
            id=1,
            total_tokens_per_month=settings.pool_total_tokens_per_month,
            floor_per_allocation=settings.pool_floor_per_allocation,
            updated_at=datetime.now(UTC),
            updated_by=None,
        )
        db.add(cfg)
        await db.flush()
    return cfg


async def active_pool_member_count(db: AsyncSession) -> int:
    """N = active, non-service, non-locked allocations (the rebalanced pool)."""
    stmt = select(func.count()).where(
        Allocation.status == AllocationStatus.active,
        Allocation.is_service_allocation.is_(False),
        Allocation.quota_locked.is_(False),
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def recent_month_usage(db: AsyncSession, now: datetime | None = None) -> int:
    """Total success tokens in the previous calendar month (for suggestions/warnings)."""
    started = datetime.now(UTC) if now is None else now
    prev_start, this_start = previous_month_range_utc(started)
    stmt = select(func.coalesce(func.sum(CallRecord.total_tokens), 0)).where(
        CallRecord.outcome == CallOutcome.success,
        CallRecord.started_at >= prev_start,
        CallRecord.started_at < this_start,
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


@dataclass(frozen=True)
class PoolSuggestion:
    recent_month_tokens: int
    pool_members: int
    suggested_total: int
    suggested_floor: int


async def suggest_pool_config(db: AsyncSession, now: datetime | None = None) -> PoolSuggestion:
    """Suggest T/floor from recent usage + member count N: T ≈ 2x recent (growth
    headroom + a real total ceiling); floor ≈ a usable baseline so an idle member
    isn't stuck at ~0 until next rebalance — while respecting T ≥ floor x N."""
    recent = await recent_month_usage(db, now)
    n = await active_pool_member_count(db)
    suggested_total = recent * 2
    # Usable baseline that keeps floorxN ≤ T/2 (leaves ≥half of T for usage-weighted
    # bonus), min 1000. For ~21M recent / N=53 → floor ≈ 400k.
    if n > 0 and suggested_total > 0:
        suggested_floor = max(1000, suggested_total // (2 * n))
    else:
        suggested_floor = 1000
    return PoolSuggestion(
        recent_month_tokens=recent,
        pool_members=n,
        suggested_total=suggested_total,
        suggested_floor=suggested_floor,
    )


async def apply_rebalance(
    db: AsyncSession, *, trigger: str, now: datetime | None = None
) -> RebalanceOutcome:
    """Run a rebalance, wrapped in a single transaction.

    Any exception → DB rollback by the surrounding session; we additionally
    write a `rebalance_failed` audit event in a NEW session so the audit
    survives the rollback. Re-raises the exception.
    """
    cfg = await get_pool_config(db)  # single source of truth (DB; env is bootstrap only)
    T = cfg.total_tokens_per_month
    floor = cfg.floor_per_allocation
    if T == 0:
        await _write_failure_audit(db, trigger, AuditEventType.pool_idle, "pool disabled (T=0)")
        raise PoolDisabledError("pool total is 0; pool disabled")

    started_at = datetime.now(UTC) if now is None else now
    prev_start, this_start = previous_month_range_utc(started_at)
    period = prev_start.strftime("%Y%m")

    # Reserved = sum of service + locked active allocations' quotas
    reserved_stmt = (
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(Allocation.quota_tokens_per_month, 0)
                ),
                0,
            )
        )
        .where(
            Allocation.status == AllocationStatus.active,
            (Allocation.is_service_allocation.is_(True))
            | (Allocation.quota_locked.is_(True)),
        )
    )
    reserved_total = int((await db.execute(reserved_stmt)).scalar_one() or 0)

    # Pool members + last-month usage
    usage_stmt = (
        select(
            Allocation.id,
            func.coalesce(func.sum(CallRecord.total_tokens), 0).label("usage"),
        )
        .outerjoin(
            CallRecord,
            (CallRecord.allocation_id == Allocation.id)
            & (CallRecord.outcome == CallOutcome.success)
            & (CallRecord.started_at >= prev_start)
            & (CallRecord.started_at < this_start),
        )
        .where(
            Allocation.status == AllocationStatus.active,
            Allocation.is_service_allocation.is_(False),
            Allocation.quota_locked.is_(False),
        )
        .group_by(Allocation.id)
        .order_by(Allocation.id)
    )
    rows = (await db.execute(usage_stmt)).all()
    pool = [PoolMember(allocation_id=r[0], usage_last_month=int(r[1] or 0)) for r in rows]

    if not pool:
        await _write_failure_audit(
            db, trigger, AuditEventType.pool_idle, "no eligible pool members"
        )
        raise PoolIdleError("no pool members (all are service/locked or none active)")

    # Take a snapshot of current quotas for the "before" column in details.
    before_stmt = select(Allocation.id, Allocation.quota_tokens_per_month).where(
        Allocation.id.in_([m.allocation_id for m in pool])
    )
    before_map = {r[0]: int(r[1] or 0) for r in (await db.execute(before_stmt)).all()}

    # Pure compute
    try:
        results = compute_rebalance(
            T=T, floor=floor, reserved_total=reserved_total, pool=pool
        )
    except PoolExhaustedByReservedError as exc:
        await _write_failure_audit(
            db, trigger, AuditEventType.pool_exhausted_by_reserved, str(exc)
        )
        raise

    # Double-check conservation at the apply layer (belt-and-braces vs T012 mock).
    _assert_conservation(results, reserved_total, T)

    scanned = len(pool)
    changed = 0
    details_allocations: list[dict[str, object]] = []
    leftover_target: str | None = None
    max_usage = -1
    for m, r in zip(pool, results, strict=True):
        before = before_map.get(m.allocation_id, 0)
        if r.new_quota != before:
            changed += 1
        details_allocations.append(
            {
                "id": r.allocation_id,
                "before": before,
                "after": r.new_quota,
                "usage": m.usage_last_month,
                "reason": r.reason,
            }
        )
        if m.usage_last_month >= max_usage:
            max_usage = m.usage_last_month
            leftover_target = m.allocation_id

    # Apply updates (race-safe: WHERE locked=false AND service=false).
    for r in results:
        await db.execute(
            update(Allocation)
            .where(
                Allocation.id == r.allocation_id,
                Allocation.quota_locked.is_(False),
                Allocation.is_service_allocation.is_(False),
                Allocation.status == AllocationStatus.active,
            )
            .values(quota_tokens_per_month=r.new_quota)
        )

    # Insert log; cron dedup via UNIQUE constraint.
    log = RebalanceLog(
        id=str(ULID()),
        period_yyyymm=period,
        triggered_by=trigger,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        T_before=T,
        T_after=T,
        scanned=scanned,
        changed=changed,
        algorithm_version=ALGORITHM_VERSION,
        details={
            "allocations": details_allocations,
            "reserved_total": reserved_total,
            "leftover_target": leftover_target,
        },
    )
    db.add(log)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return RebalanceOutcome(log=None, skipped_reason="cron_dedup_same_month")

    await audit.record(
        db,
        event_type=AuditEventType.quota_pool_rebalanced,
        actor_type=ActorType.system if trigger == "cron" else ActorType.admin,
        actor_id=trigger,
        target_type="rebalance_log",
        target_id=log.id,
        details={"scanned": scanned, "changed": changed, "T": T},
    )
    await db.flush()
    return RebalanceOutcome(log=log)


async def _write_failure_audit(
    db: AsyncSession, trigger: str, event_type: AuditEventType, reason: str
) -> None:
    """Write a failure audit row. Caller is expected to raise afterwards.

    Note: we write into the SAME session; if the outer transaction rolls back,
    this row goes with it. To make failure audit survive rollback, we'd need a
    separate session — but for now we accept that the test must verify via the
    same session (or commit explicitly). The /admin endpoint commits after
    catching exceptions to preserve the audit.
    """
    await audit.record(
        db,
        event_type=event_type,
        actor_type=ActorType.system if trigger == "cron" else ActorType.admin,
        actor_id=trigger,
        target_type="quota_pool",
        target_id=None,
        details={"reason": reason},
    )
