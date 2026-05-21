"""Allocation admin endpoints."""
from __future__ import annotations

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
    created = await service.create(
        subject=payload.subject,
        resource_model=payload.resource_model,
        note=payload.note,
    )
    return AllocationCreatedOut(
        id=created.allocation.id,
        subject=created.allocation.subject,
        resource_model=created.allocation.resource_model,
        status=created.allocation.status,
        created_at=created.allocation.created_at,
        revoked_at=created.allocation.revoked_at,
        created_by=created.allocation.created_by,
        note=created.allocation.note,
        token_prefix=created.allocation.credential.token_prefix,
        token=created.token.plaintext,
    )


@router.get("/allocations", response_model=list[AllocationOut])
async def list_allocations(
    subject: str | None = Query(default=None),
    status_q: AllocationStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[AllocationOut]:
    service = AllocationService(session)
    allocations = await service.list(subject=subject, status=status_q)
    return [
        AllocationOut(
            id=a.id,
            subject=a.subject,
            resource_model=a.resource_model,
            status=a.status,
            created_at=a.created_at,
            revoked_at=a.revoked_at,
            created_by=a.created_by,
            note=a.note,
            token_prefix=a.credential.token_prefix,
        )
        for a in allocations
    ]


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
    return AllocationOut(
        id=allocation.id,
        subject=allocation.subject,
        resource_model=allocation.resource_model,
        status=allocation.status,
        created_at=allocation.created_at,
        revoked_at=allocation.revoked_at,
        created_by=allocation.created_by,
        note=allocation.note,
        token_prefix=allocation.credential.token_prefix,
    )
