"""RecordsService: persist + query CallRecord rows."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import select
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
            stmt = stmt.where(CallRecord.id < before)
        result = await self._s.execute(stmt)
        return cast(list[CallRecord], list(result.scalars().all()))
