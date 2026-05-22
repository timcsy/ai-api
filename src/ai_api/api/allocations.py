"""Allocation admin endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.api.schemas import (
    AllocationCreatedOut,
    AllocationOut,
    CreateAllocationRequest,
)
from ai_api.models import AllocationStatus
from ai_api.services.allocations import AllocationService

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _to_out(a: Any) -> AllocationOut:
    return AllocationOut(
        id=a.id,
        member_id=a.member_id,
        subject_snapshot=a.subject_snapshot,
        resource_model=a.resource_model,
        status=a.status,
        created_at=a.created_at,
        revoked_at=a.revoked_at,
        created_by=a.created_by,
        note=a.note,
        token_prefix=a.credential.token_prefix,
    )


@router.post(
    "/allocations",
    response_model=AllocationCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_allocation(
    payload: CreateAllocationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AllocationCreatedOut:
    service = AllocationService(session)
    try:
        created = await service.create(
            member_id=payload.member_id,
            subject=payload.subject,
            resource_model=payload.resource_model,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "member_not_found", "message": str(exc)}},
        ) from exc
    base = _to_out(created.allocation).model_dump()
    base.pop("subject", None)  # 'subject' is a computed_field; not constructor arg
    return AllocationCreatedOut(**base, token=created.token.plaintext)


@router.get("/allocations", response_model=list[AllocationOut])
async def list_allocations(
    member_id: str | None = Query(default=None),
    status_q: AllocationStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[AllocationOut]:
    service = AllocationService(session)
    allocations = await service.list(member_id=member_id, status=status_q)
    return [_to_out(a) for a in allocations]


@router.delete("/allocations/{allocation_id}", response_model=AllocationOut)
async def revoke_allocation(
    allocation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AllocationOut:
    service = AllocationService(session)
    allocation = await service.revoke(allocation_id)
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    return _to_out(allocation)


@router.post("/allocations/{allocation_id}/unquarantine", response_model=AllocationOut)
async def unquarantine_allocation(
    allocation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AllocationOut:
    """Manually clear `quarantined` status back to `active`."""
    from ai_api.auth import audit
    from ai_api.models import ActorType, AuditEventType

    service = AllocationService(session)
    allocation = await service.get(allocation_id)
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    if allocation.status != AllocationStatus.quarantined:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "not_quarantined",
                    "message": f"allocation is {allocation.status.value}, not quarantined",
                }
            },
        )
    allocation.status = AllocationStatus.active
    await audit.record(
        session,
        event_type=AuditEventType.allocation_unquarantined,
        actor_type=ActorType.admin,
        target_type="allocation",
        target_id=allocation.id,
    )
    await session.flush()
    return _to_out(allocation)
