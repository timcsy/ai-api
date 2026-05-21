"""Call record admin endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.api.schemas import CallRecordOut
from ai_api.services.allocations import AllocationService
from ai_api.services.records import RecordsService

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
    return [
        CallRecordOut(
            id=r.id,
            request_id=r.request_id,
            allocation_id=r.allocation_id,
            subject=r.subject,
            model=r.model,
            started_at=r.started_at,
            finished_at=r.finished_at,
            status_code=r.status_code,
            outcome=r.outcome.value,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            error_message=r.error_message,
        )
        for r in records
    ]
