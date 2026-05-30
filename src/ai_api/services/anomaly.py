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


async def evaluate_allocation(
    db: AsyncSession, allocation_id: str, now: datetime | None = None
) -> QuarantineDecision | None:
    settings = get_settings()
    now = now or datetime.now(UTC)
    last_hour_start = now - timedelta(hours=1)
    baseline_window_start = now - timedelta(hours=24)

    last_hour = await _count_calls(db, allocation_id, last_hour_start, now)
    if last_hour < settings.anomaly_min_calls:
        return None

    baseline_total = await _count_calls(
        db, allocation_id, baseline_window_start, last_hour_start
    )
    # 23 hours of baseline window (24h total minus last hour)
    baseline_per_hour = baseline_total / 23.0

    if baseline_per_hour == 0:
        # cold-start: use absolute threshold
        if last_hour >= settings.anomaly_absolute_cold_start:
            return QuarantineDecision(
                allocation_id=allocation_id,
                last_hour_calls=last_hour,
                baseline_per_hour=0.0,
                reason="absolute_cold_start",
            )
        return None

    if last_hour >= baseline_per_hour * settings.anomaly_threshold_multiplier:
        return QuarantineDecision(
            allocation_id=allocation_id,
            last_hour_calls=last_hour,
            baseline_per_hour=baseline_per_hour,
            reason="ratio",
        )
    return None


async def detect_and_quarantine(db: AsyncSession) -> list[QuarantineDecision]:
    """One scan pass. Returns list of allocations that were quarantined."""
    now = datetime.now(UTC)
    # Only consider active, non-service allocations. Service allocations
    # (e.g. agent CLIs like Codex, internal bots) are exempt — their traffic
    # is bursty by design and would otherwise be flagged as anomalous.
    active_stmt = select(Allocation).where(
        Allocation.status == AllocationStatus.active,
        Allocation.is_service_allocation.is_(False),
    )
    allocations = (await db.execute(active_stmt)).scalars().all()

    decisions: list[QuarantineDecision] = []
    for alloc in allocations:
        decision = await evaluate_allocation(db, alloc.id, now=now)
        if decision is None:
            continue
        alloc.status = AllocationStatus.quarantined
        decisions.append(decision)
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
            "quarantined": len(decisions),
        },
    )
    await db.flush()
    return decisions
