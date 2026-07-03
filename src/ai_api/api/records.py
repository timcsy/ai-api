"""Call record admin endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.api.schemas import CallRecordOut
from ai_api.services.allocations import AllocationService
from ai_api.services.records import RecordsService


def _record_out(r: Any) -> CallRecordOut:
    return CallRecordOut(
        id=r.id, request_id=r.request_id, allocation_id=r.allocation_id, subject=r.subject,
        model=r.model, started_at=r.started_at, finished_at=r.finished_at,
        status_code=r.status_code, outcome=r.outcome.value,
        prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
        total_tokens=r.total_tokens, reasoning_tokens=r.reasoning_tokens,
        cached_tokens=r.cached_tokens, cost_usd=r.cost_usd, quantity=r.quantity, unit=r.unit,
        error_message=r.error_message,
    )

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("/allocations/{allocation_id}/calls", response_model=list[CallRecordOut])
async def list_allocation_calls(
    allocation_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    before: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[CallRecordOut]:
    # Validate allocation exists, else 404
    alloc_service = AllocationService(session)
    if await alloc_service.get(allocation_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    records_service = RecordsService(session)
    records = await records_service.list_for_allocation(
        allocation_id=allocation_id, limit=limit, before=before
    )
    return [_record_out(r) for r in records]


@router.get("/records")
async def list_records(
    member_id: str | None = Query(default=None),
    allocation_id: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    outcome: str | None = Query(default=None, description="filter by outcome, e.g. success"),
    limit: int = Query(default=100, ge=1, le=200),
    before: str | None = Query(default=None, description="keyset cursor (record id)"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Per-call records across members/allocations (admin). Cursor-paginated on
    (started_at DESC, id DESC); each item carries per-record cost + unit (spec 056)."""
    records = await RecordsService(session).list_records(
        member_id=member_id, allocation_id=allocation_id, subject=subject,
        from_=from_, to=to, outcome=outcome, limit=limit + 1, before=before,
    )
    has_more = len(records) > limit
    items = records[:limit]
    return {
        "items": [_record_out(r) for r in items],
        "next_before": items[-1].id if has_more and items else None,
    }
