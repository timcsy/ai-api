"""Phase 13 US3: upstream error-burst detector.

Scans recent CallRecord rows for a spike of `upstream_error` outcomes within a
sliding window. When the count crosses the threshold, emits a single
`responses_upstream_error_burst` audit event (which the notifier hook turns into
an admin email). Designed to run as a K8s CronJob (every minute), mirroring the
anomaly detector pattern.

To avoid re-alerting every minute for an ongoing outage, the detector suppresses
a new burst event if one was already emitted within the last `window_minutes`.
(The notifier's own 5-min dedup is a second layer; this keeps audit noise down.)
"""
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
    AuditEventType,
    AuthAuditLog,
    CallOutcome,
    CallRecord,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BurstDecision:
    failure_count: int
    window_minutes: int
    latest_model: str | None


async def detect_upstream_burst(
    db: AsyncSession, now: datetime | None = None
) -> BurstDecision | None:
    """One scan pass. Emits a burst audit event if the threshold is crossed and
    no burst event was emitted within the window. Returns the decision or None."""
    settings = get_settings()
    threshold = settings.upstream_burst_threshold
    window_minutes = settings.upstream_burst_window_minutes
    now = now or datetime.now(UTC)
    window_start = now - timedelta(minutes=window_minutes)

    count_stmt = (
        select(func.count())
        .select_from(CallRecord)
        .where(
            CallRecord.outcome == CallOutcome.upstream_error,
            CallRecord.started_at >= window_start,
            CallRecord.started_at <= now,
        )
    )
    failure_count = int((await db.execute(count_stmt)).scalar_one())
    if failure_count < threshold:
        return None

    # Suppress if a burst event already fired within the window (avoid per-minute spam).
    recent_burst_stmt = (
        select(func.count())
        .select_from(AuthAuditLog)
        .where(
            AuthAuditLog.event_type == AuditEventType.responses_upstream_error_burst,
            AuthAuditLog.created_at >= window_start,
        )
    )
    recent_bursts = int((await db.execute(recent_burst_stmt)).scalar_one())
    if recent_bursts > 0:
        logger.info(
            "upstream burst threshold crossed (count=%d) but suppressed: "
            "a burst event already fired within %d min",
            failure_count, window_minutes,
        )
        return None

    # Find the most recent failing model for context.
    latest_model_stmt = (
        select(CallRecord.model)
        .where(
            CallRecord.outcome == CallOutcome.upstream_error,
            CallRecord.started_at >= window_start,
        )
        .order_by(CallRecord.started_at.desc())
        .limit(1)
    )
    latest_model = (await db.execute(latest_model_stmt)).scalar_one_or_none()

    decision = BurstDecision(
        failure_count=failure_count,
        window_minutes=window_minutes,
        latest_model=latest_model,
    )
    await audit.record(
        db,
        event_type=AuditEventType.responses_upstream_error_burst,
        actor_type=ActorType.system,
        target_type="upstream",
        target_id=latest_model,
        details={
            "failure_count": failure_count,
            "window_minutes": window_minutes,
            "latest_model": latest_model,
        },
    )
    logger.warning(
        "upstream error burst detected: %d failures in %d min (latest_model=%s)",
        failure_count, window_minutes, latest_model,
    )
    return decision
