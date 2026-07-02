"""Anomaly detector: scan recent CallRecord traffic and quarantine outliers."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.auth import audit
from ai_api.config import get_settings
from ai_api.models import (
    ActorType,
    Allocation,
    AllocationStatus,
    AnomalyConfig,
    AuditEventType,
    CallOutcome,
    CallRecord,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuarantineDecision:
    allocation_id: str
    last_hour_calls: int
    baseline_per_hour: float
    reason: str  # "ratio" | "absolute_cold_start"


async def _count_calls(
    db: AsyncSession, allocation_id: str, since: datetime, until: datetime
) -> int:
    stmt = (
        select(func.count())
        .select_from(CallRecord)
        .where(
            CallRecord.allocation_id == allocation_id,
            CallRecord.started_at >= since,
            CallRecord.started_at < until,
            CallRecord.outcome == CallOutcome.success,
        )
    )
    return int((await db.execute(stmt)).scalar_one())


async def get_anomaly_config(db: AsyncSession) -> AnomalyConfig:
    """The singleton anomaly config (switch + pause + thresholds). Lazy-seeds from
    settings on first access so the move env→DB is a no-op on first run; thereafter
    the DB row is the single source of truth (env is bootstrap default only)."""
    cfg = await db.get(AnomalyConfig, 1)
    if cfg is None:
        settings = get_settings()
        cfg = AnomalyConfig(
            id=1,
            auto_quarantine_enabled=True,
            pause_until=None,
            threshold_multiplier=settings.anomaly_threshold_multiplier,
            min_calls=settings.anomaly_min_calls,
            absolute_cold_start=settings.anomaly_absolute_cold_start,
            baseline_min_calls=200,
            updated_at=datetime.now(UTC),
            updated_by=None,
        )
        db.add(cfg)
        await db.flush()
    return cfg


async def evaluate_allocation(
    db: AsyncSession,
    allocation_id: str,
    now: datetime | None = None,
    cfg: AnomalyConfig | None = None,
) -> QuarantineDecision | None:
    now = now or datetime.now(UTC)
    if cfg is None:
        cfg = await get_anomaly_config(db)
    last_hour_start = now - timedelta(hours=1)
    baseline_window_start = now - timedelta(hours=24)

    last_hour = await _count_calls(db, allocation_id, last_hour_start, now)
    if last_hour < cfg.min_calls:
        return None

    baseline_total = await _count_calls(
        db, allocation_id, baseline_window_start, last_hour_start
    )
    # 23 hours of baseline window (24h total minus last hour)
    baseline_per_hour = baseline_total / 23.0

    # Sparse baseline (incl. cold-start, freshly-migrated cluster, new allocation):
    # too few samples to trust the ratio → use the absolute threshold only. This
    # is what stops workshop/onboarding spikes from being false-flagged, while a
    # genuinely runaway caller (>= absolute) is still caught.
    if baseline_total < cfg.baseline_min_calls:
        if last_hour >= cfg.absolute_cold_start:
            return QuarantineDecision(
                allocation_id=allocation_id,
                last_hour_calls=last_hour,
                baseline_per_hour=baseline_per_hour,
                reason="absolute_cold_start",
            )
        return None

    if last_hour >= baseline_per_hour * cfg.threshold_multiplier:
        return QuarantineDecision(
            allocation_id=allocation_id,
            last_hour_calls=last_hour,
            baseline_per_hour=baseline_per_hour,
            reason="ratio",
        )
    return None


async def detect_and_quarantine(db: AsyncSession) -> list[QuarantineDecision]:
    """One scan pass. Returns list of allocations that were quarantined.

    When enforcement is disabled or paused (admin control), the scan still runs
    and flags outliers in the logs/audit, but does NOT quarantine anyone."""
    now = datetime.now(UTC)
    cfg = await get_anomaly_config(db)
    enforcing = cfg.effective_enforcing(now)
    # Only consider active, non-service allocations. Service allocations
    # (e.g. agent CLIs like Codex, internal bots) are exempt — their traffic
    # is bursty by design and would otherwise be flagged as anomalous.
    active_stmt = select(Allocation).where(
        Allocation.status == AllocationStatus.active,
        Allocation.is_service_allocation.is_(False),
    )
    allocations = (await db.execute(active_stmt)).scalars().all()

    quarantined: list[QuarantineDecision] = []
    flagged = 0
    for alloc in allocations:
        decision = await evaluate_allocation(db, alloc.id, now=now, cfg=cfg)
        if decision is None:
            continue
        flagged += 1
        if not enforcing:
            # Admin has disabled/paused auto-quarantine — detect but don't block.
            logger.info(
                "anomaly flagged but enforcement %s: allocation=%s last_hour=%d reason=%s",
                cfg.status(now),
                alloc.id,
                decision.last_hour_calls,
                decision.reason,
            )
            continue
        alloc.status = AllocationStatus.quarantined
        quarantined.append(decision)
        await audit.record(
            db,
            event_type=AuditEventType.allocation_quarantined,
            actor_type=ActorType.system,
            target_type="allocation",
            target_id=alloc.id,
            details={
                "trigger": "anomaly_detector",
                "last_hour_calls": decision.last_hour_calls,
                "baseline_per_hour": decision.baseline_per_hour,
                "reason": decision.reason,
            },
        )
        logger.warning(
            "quarantined allocation %s reason=%s last_hour=%d baseline=%.2f/hr",
            alloc.id,
            decision.reason,
            decision.last_hour_calls,
            decision.baseline_per_hour,
        )

    await audit.record(
        db,
        event_type=AuditEventType.anomaly_detector_run,
        actor_type=ActorType.system,
        details={
            "scanned": len(allocations),
            "flagged": flagged,
            "quarantined": len(quarantined),
            "enforced": enforcing,
        },
    )
    await db.flush()
    return quarantined
