"""RecordsService: persist + query CallRecord rows."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import CallOutcome, CallRecord
from ai_api.observability.logging import redact_string


class RecordsService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record_call(
        self,
        *,
        request_id: str,
        allocation_id: str | None,
        subject: str | None,
        model: str | None,
        started_at: datetime,
        status_code: int,
        outcome: CallOutcome,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        reasoning_tokens: int | None = None,
        cached_tokens: int | None = None,
        quantity: int | None = None,
        unit: str | None = None,
        error_message: str | None = None,
        cost_usd: Decimal | None = None,
    ) -> CallRecord:
        record = CallRecord(
            id=str(ULID()),
            request_id=request_id or "unknown",
            allocation_id=allocation_id,
            subject=subject,
            model=model,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            status_code=status_code,
            outcome=outcome,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            reasoning_tokens=reasoning_tokens,
            cached_tokens=cached_tokens,
            quantity=quantity,
            unit=unit,
            cost_usd=cost_usd,
            error_message=redact_string(error_message) if error_message else None,
        )
        self._s.add(record)
        await self._s.flush()
        return record

    async def list_for_allocation(
        self,
        allocation_id: str,
        limit: int = 100,
        before: str | None = None,
    ) -> list[CallRecord]:
        stmt = (
            select(CallRecord)
            .where(CallRecord.allocation_id == allocation_id)
            .order_by(CallRecord.started_at.desc(), CallRecord.id.desc())
            .limit(limit)
        )
        if before:
            # Keyset cursor MUST match the sort key (started_at DESC, id DESC).
            # Filtering on `id` alone is wrong: ULIDs minted in the same
            # millisecond order by their random suffix, not by started_at, so an
            # `id < before` boundary returns a non-deterministic row count. Page
            # strictly *after* the pivot row in (started_at, id) order instead.
            pivot_started_at = (
                select(CallRecord.started_at).where(CallRecord.id == before).scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    CallRecord.started_at < pivot_started_at,
                    and_(
                        CallRecord.started_at == pivot_started_at,
                        CallRecord.id < before,
                    ),
                )
            )
        result = await self._s.execute(stmt)
        return cast(list[CallRecord], list(result.scalars().all()))
