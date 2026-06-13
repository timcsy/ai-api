"""Monthly quota service for allocations."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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


async def current_month_cost(db: AsyncSession, allocation_id: str) -> Decimal:
    """Total successful `cost_usd` for this allocation since UTC month start (Phase 33).

    Cross-unit common denominator: token + non-token (page/image/second/minute/char)
    calls all carry cost_usd, so summing it governs every endpoint with one cap.
    Unpriced calls have cost_usd NULL → coalesce(0) → they don't accrue and aren't
    governed by the cost cap (honest; admin must price them to bring them in scope)."""
    start = current_month_start_utc()
    stmt = select(func.coalesce(func.sum(CallRecord.cost_usd), 0)).where(
        CallRecord.allocation_id == allocation_id,
        CallRecord.outcome == CallOutcome.success,
        CallRecord.started_at >= start,
    )
    # str() guard: coerce exactly even if a backend hands back a float for the sum.
    return Decimal(str((await db.execute(stmt)).scalar_one() or 0))


def is_over_cost_quota(allocation: Allocation, current_cost: Decimal) -> bool:
    """cost cap=None → unlimited; otherwise check >= cap (mirrors is_over_quota)."""
    if allocation.quota_cost_usd_per_month is None:
        return False
    return current_cost >= allocation.quota_cost_usd_per_month
