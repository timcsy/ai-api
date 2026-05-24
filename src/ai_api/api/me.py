"""Member self-service endpoints (/me*)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import current_member, get_db_session, require_csrf
from ai_api.auth import local
from ai_api.models import Member, MemberProvider
from ai_api.services.allocations import AllocationService
from ai_api.services.records import RecordsService

router = APIRouter()


def _member_public(m: Member) -> dict[str, Any]:
    return {
        "id": m.id,
        "email": m.email,
        "provider": m.provider,
        "display_name": m.display_name,
        "status": m.status,
    }


@router.get("/me")
async def get_me(member: Member = Depends(current_member)) -> dict[str, Any]:
    return _member_public(member)


@router.get("/me/allocations")
async def list_my_allocations(
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    allocations = await AllocationService(db).list(member_id=member.id)
    return [
        {
            "id": a.id,
            "member_id": a.member_id,
            "subject_snapshot": a.subject_snapshot,
            "resource_model": a.resource_model,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "revoked_at": a.revoked_at.isoformat() if a.revoked_at else None,
            "token_prefix": a.credential.token_prefix,
        }
        for a in allocations
    ]


@router.get("/me/allocations/{allocation_id}/calls")
async def list_my_allocation_calls(
    allocation_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    before_id: str | None = Query(default=None),
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Cursor-paginated CallRecord history for the member's own allocation."""
    allocation = await AllocationService(db).get(allocation_id)
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    if allocation.member_id != member.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "not your allocation"}},
        )
    # Fetch limit+1 to detect whether there's a next page.
    records = await RecordsService(db).list_for_allocation(
        allocation_id, limit=limit + 1, before=before_id
    )
    has_more = len(records) > limit
    items = records[:limit]
    next_before_id = items[-1].id if has_more and items else None
    return {
        "items": [
            {
                "id": r.id,
                "request_id": r.request_id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat(),
                "status_code": r.status_code,
                "outcome": r.outcome,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
            }
            for r in items
        ],
        "next_before_id": next_before_id,
    }


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def change_password(
    payload: ChangePasswordRequest,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    # Re-fetch in request session — `member` came from a different (closed) session.
    fresh = await db.get(Member, member.id)
    if fresh is None or fresh.provider != MemberProvider.local_password or fresh.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "no_password", "message": "this account cannot change a password"}},
        )
    if not local.verify_password(fresh.password_hash, payload.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_old_password", "message": "old password incorrect"}},
        )
    try:
        local.enforce_policy(payload.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "weak_password", "message": str(exc)}},
        ) from exc
    fresh.password_hash = local.hash_password(payload.new_password)
    await db.flush()
