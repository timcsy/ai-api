"""Monthly quota service for allocations."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import Allocation, CallOutcome, CallRecord


def current_month_start_utc(now: datetime | None = None) -> datetime:
    """Return the UTC datetime at the start of the current calendar month."""
    n = now or datetime.now(UTC)
    return datetime(n.year, n.month, 1, tzinfo=UTC)


async def current_month_usage(db: AsyncSession, allocation_id: str) -> int:
    """Total successful `total_tokens` for this allocation since UTC month start."""
    start = current_month_start_utc()
    stmt = select(func.coalesce(func.sum(CallRecord.total_tokens), 0)).where(
        CallRecord.allocation_id == allocation_id,
        CallRecord.outcome == CallOutcome.success,
        CallRecord.started_at >= start,
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


def is_over_quota(allocation: Allocation, current_usage: int) -> bool:
    """quota=None → unlimited; otherwise check >= cap."""
    if allocation.quota_tokens_per_month is None:
        return False
    return current_usage >= allocation.quota_tokens_per_month
