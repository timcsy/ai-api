"""StoredResponseService — Phase 11 server-side conversation state (store).

Keeps a `response_id → allocation` mapping so `previous_response_id` continuations
are attribution-isolated. We key by the upstream (provider) response id, which is
what the client sees and sends back, so no id rewriting is needed — only an
ownership check before the id is passed through to the upstream.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import StoredResponse

DEFAULT_TTL_DAYS = 30

ContinuationResult = str | Literal["not_found", "forbidden"]


def _aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; coerce naive to UTC for comparison."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class StoredResponseService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def store(
        self,
        *,
        allocation_id: str,
        provider: str,
        upstream_response_id: str,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> str:
        """Persist ownership of a response id. Returns the response id."""
        now = datetime.now(UTC)
        row = StoredResponse(
            response_id=upstream_response_id,
            allocation_id=allocation_id,
            provider=provider,
            upstream_response_id=upstream_response_id,
            created_at=now,
            expires_at=now + timedelta(days=ttl_days),
        )
        await self._s.merge(row)
        await self._s.flush()
        return upstream_response_id

    async def resolve_for_continuation(
        self, *, response_id: str, allocation_id: str, provider: str
    ) -> ContinuationResult:
        """Return the upstream id to continue with, or a rejection reason.

        - not_found: unknown or expired
        - forbidden: exists but owned by a different allocation (or provider)
        """
        row = await self._s.get(StoredResponse, response_id)
        if row is None or _aware(row.expires_at) <= datetime.now(UTC):
            return "not_found"
        if row.allocation_id != allocation_id or row.provider != provider:
            return "forbidden"
        return row.upstream_response_id or row.response_id

    async def cleanup_expired(self) -> int:
        """Delete all expired rows. Returns count removed."""
        now = datetime.now(UTC)
        rows = (
            await self._s.execute(select(StoredResponse))
        ).scalars().all()
        removed = 0
        for r in rows:
            if _aware(r.expires_at) <= now:
                await self._s.delete(r)
                removed += 1
        await self._s.flush()
        return removed
