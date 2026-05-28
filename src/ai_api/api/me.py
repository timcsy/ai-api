"""Member self-service endpoints (/me*)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import current_member, get_db_session, require_csrf
from ai_api.auth import local
from ai_api.config import get_settings
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
        "is_admin": m.is_admin,
        # Phase 5+: surface the canonical gateway base URL so the dashboard
        # can show the correct endpoint instead of guessing window.location.origin
        # (which on dev resolves to the Vite port, not the backend).
        "gateway_base_url": get_settings().base_url.rstrip("/"),
    }


@router.get("/me")
async def get_me(member: Member = Depends(current_member)) -> dict[str, Any]:
    return _member_public(member)


def _alloc_public(
    a: Any, price: dict[str, str] | None = None, display_name: str | None = None
) -> dict[str, Any]:
    return {
        "id": a.id,
        "member_id": a.member_id,
        "subject_snapshot": a.subject_snapshot,
        "resource_model": a.resource_model,
        "display_name": display_name,  # catalog display name, or null if orphan
        "status": a.status,
        "origin": a.origin,
        "quota_tokens_per_month": a.quota_tokens_per_month,
        "created_at": a.created_at.isoformat(),
        "revoked_at": a.revoked_at.isoformat() if a.revoked_at else None,
        "token_prefix": a.credential.token_prefix,
        "price": price,  # current per-1K price of the resource_model, or null
    }


def _provider_of(slug: str) -> str:
    return slug.split("/", 1)[0] if "/" in slug else ""


@router.get("/me/allocations")
async def list_my_allocations(
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    from datetime import UTC, datetime

    from sqlalchemy import select

    from ai_api.models import ModelCatalog
    from ai_api.services import pricing

    allocations = await AllocationService(db).list(member_id=member.id)
    price_map = await pricing.current_price_map(db, datetime.now(UTC))
    # slug → display_name from the catalog (orphan slugs absent → None)
    name_rows = await db.execute(select(ModelCatalog.slug, ModelCatalog.display_name))
    name_map: dict[str, str] = {row[0]: row[1] for row in name_rows.all()}
    return [
        _alloc_public(
            a,
            pricing.price_for_slug(price_map, _provider_of(a.resource_model), a.resource_model),
            name_map.get(a.resource_model),
        )
        for a in allocations
    ]


def _summary_dict(row: Any, has_unpriced: bool) -> dict[str, Any]:
    if row is None:
        return {
            "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "reasoning_tokens": 0, "cached_tokens": 0,
            "total_cost_usd": 0.0, "call_count": 0, "has_unpriced": False,
        }
    return {
        "total_tokens": row.total_tokens,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "reasoning_tokens": row.reasoning_tokens,
        "cached_tokens": row.cached_tokens,
        "total_cost_usd": float(row.total_cost_usd),
        "call_count": row.call_count,
        "has_unpriced": has_unpriced,
    }


@router.get("/me/usage")
async def get_my_usage(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    group_by: Literal["model", "allocation"] | None = Query(default=None),
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """This member's own usage, strictly scoped to them (Phase 018).

    Default range = current month (UTC). `group_by` adds a per-model / per-
    allocation breakdown. Range/scope come from the session — there is no
    parameter to view another member's usage.
    """
    from ai_api.api.usage import _validate_range
    from ai_api.services.usage import aggregate_usage, count_unpriced_calls

    now = datetime.now(UTC)
    to = to or now
    from_ = from_ or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _validate_range(from_, to)

    summary_rows = await aggregate_usage(
        db, group_by="member", from_=from_, to=to, member_id=member.id
    )
    unpriced = await count_unpriced_calls(db, member_id=member.id, from_=from_, to=to)
    result: dict[str, Any] = {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "summary": _summary_dict(summary_rows[0] if summary_rows else None, unpriced > 0),
    }
    if group_by is not None:
        items = await aggregate_usage(
            db, group_by=group_by, from_=from_, to=to, member_id=member.id
        )
        result["breakdown"] = [
            {
                "group_key": it.group_key,
                "display_name": it.display_name,
                "total_tokens": it.total_tokens,
                "prompt_tokens": it.prompt_tokens,
                "completion_tokens": it.completion_tokens,
                "reasoning_tokens": it.reasoning_tokens,
                "cached_tokens": it.cached_tokens,
                "total_cost_usd": float(it.total_cost_usd),
                "call_count": it.call_count,
            }
            for it in items
        ]
    return result


@router.get("/me/claimable-models")
async def list_claimable_models(
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Self-service-opened models visible to this member, with claim state."""
    from ai_api.services.self_service import SelfServiceService

    return await SelfServiceService(db).list_claimable(member)


class ClaimRequest(BaseModel):
    model: str


_CLAIM_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "model_forbidden": status.HTTP_403_FORBIDDEN,
    "model_not_self_service": status.HTTP_403_FORBIDDEN,
    "member_inactive": status.HTTP_403_FORBIDDEN,
    "reclaim_locked": status.HTTP_403_FORBIDDEN,
}


@router.post("/me/allocations", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def claim_allocation(
    payload: ClaimRequest,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from ai_api.services.self_service import ClaimError, SelfServiceService

    svc = SelfServiceService(db)
    try:
        created = await svc.claim(member, payload.model)
    except ClaimError as exc:
        if exc.reason == "already_claimed":
            existing = await svc.existing_active(member.id, payload.model)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {"code": "already_claimed", "message": "you already hold an active self-service allocation for this model"},
                    "allocation": _alloc_public(existing) if existing else None,
                },
            ) from exc
        raise HTTPException(
            status_code=_CLAIM_STATUS.get(exc.reason, status.HTTP_403_FORBIDDEN),
            detail={"error": {"code": exc.reason, "message": f"cannot claim: {exc.reason}"}},
        ) from exc
    return {"token": created.token.plaintext, "allocation": _alloc_public(created.allocation)}


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


@router.post(
    "/me/allocations/{allocation_id}/rotate-token",
    dependencies=[Depends(require_csrf)],
)
async def rotate_my_allocation_token(
    allocation_id: str,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Issue a new token for this member's own allocation. Old token immediately
    invalid. Returns the new plaintext token ONCE — UI must store it client-side
    if needed; we hash it in DB."""
    from ai_api.auth import audit
    from ai_api.models import ActorType, AuditEventType

    service = AllocationService(db)
    allocation = await service.get(allocation_id)
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
    try:
        result = await service.rotate_token(allocation_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "cannot_rotate", "message": str(exc)}},
        ) from exc
    assert result is not None
    _, token = result
    await audit.record(
        db,
        event_type=AuditEventType.allocation_token_rotated,
        actor_type=ActorType.member,
        actor_id=member.id,
        target_type="allocation",
        target_id=allocation_id,
    )
    return {"token": token.plaintext, "token_prefix": token.prefix}


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
