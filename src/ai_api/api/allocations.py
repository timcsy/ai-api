"""Allocation admin endpoints."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.api.schemas import (
    AllocationCreatedOut,
    AllocationOut,
    CreateAllocationRequest,
    CredentialOut,
)
from ai_api.auth import audit
from ai_api.models import ActorType, AllocationStatus, AuditEventType
from ai_api.services.allocations import AllocationService

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _repr_token_prefix(a: Any) -> str | None:
    """Phase 18: pick a representative credential prefix for legacy single-prefix
    display — first active credential, else the first one (none → None)."""
    creds = list(a.credentials)
    if not creds:
        return None
    active = next((c for c in creds if c.revoked_at is None), None)
    prefix: str = (active or creds[0]).token_prefix
    return prefix


def _to_out(a: Any, display_name: str | None = None) -> AllocationOut:
    return AllocationOut(
        id=a.id,
        member_id=a.member_id,
        subject_snapshot=a.subject_snapshot,
        resource_model=a.resource_model,
        display_name=display_name,
        status=a.status,
        created_at=a.created_at,
        revoked_at=a.revoked_at,
        created_by=a.created_by,
        note=a.note,
        token_prefix=_repr_token_prefix(a),
        quota_tokens_per_month=a.quota_tokens_per_month,
        quota_cost_usd_per_month=a.quota_cost_usd_per_month,
        is_service_allocation=a.is_service_allocation,
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
            quota_cost_usd_per_month=payload.quota_cost_usd_per_month,
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
    # Catalog slug → display_name so admin tables can show a friendly name.
    from sqlalchemy import select

    from ai_api.models import ModelCatalog

    name_rows = await session.execute(select(ModelCatalog.slug, ModelCatalog.display_name))
    name_map: dict[str, str] = {row[0]: row[1] for row in name_rows.all()}
    return [_to_out(a, name_map.get(a.resource_model)) for a in allocations]


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


@router.post("/allocations/{allocation_id}/pause", response_model=AllocationOut)
async def pause_allocation(
    allocation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AllocationOut:
    """Reversibly pause an active allocation (keeps the same token)."""
    from ai_api.services.allocations import InvalidAllocationState

    service = AllocationService(session)
    try:
        allocation = await service.pause(allocation_id)
    except InvalidAllocationState as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "invalid_state", "message": str(exc)}},
        ) from exc
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    return _to_out(allocation)


@router.post("/allocations/{allocation_id}/resume", response_model=AllocationOut)
async def resume_allocation(
    allocation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AllocationOut:
    """Resume a paused allocation back to active (original token works again)."""
    from ai_api.services.allocations import InvalidAllocationState

    service = AllocationService(session)
    try:
        allocation = await service.resume(allocation_id)
    except InvalidAllocationState as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "invalid_state", "message": str(exc)}},
        ) from exc
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    return _to_out(allocation)


@router.patch("/allocations/{allocation_id}", response_model=AllocationOut)
async def patch_allocation(
    allocation_id: str,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
) -> AllocationOut:
    """Update mutable allocation fields. Accepts:
    - quota_tokens_per_month (int | null) — null = unlimited
    - quota_cost_usd_per_month (number | null) — null = no cost cap (Phase 33)
    - is_service_allocation (bool)
    - note (str)
    """

    allowed = {"quota_tokens_per_month", "quota_cost_usd_per_month", "is_service_allocation", "note"}
    unknown = set(payload.keys()) - allowed
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "bad_request", "message": f"unknown fields: {sorted(unknown)}"}},
        )
    service = AllocationService(session)
    allocation = await service.get(allocation_id)
    if allocation is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    if "quota_tokens_per_month" in payload:
        v = payload["quota_tokens_per_month"]
        if v is not None and (not isinstance(v, int) or v < 0):
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "bad_request", "message": "quota_tokens_per_month must be int >= 0 or null"}},
            )
        allocation.quota_tokens_per_month = v
    if "quota_cost_usd_per_month" in payload:
        cv = payload["quota_cost_usd_per_month"]
        if cv is not None:
            try:
                cv = Decimal(str(cv))
            except (ArithmeticError, ValueError, TypeError):
                cv = Decimal(-1)
            if cv < 0:
                raise HTTPException(
                    status_code=400,
                    detail={"error": {"code": "bad_request",
                                      "message": "quota_cost_usd_per_month must be a number >= 0 or null"}},
                )
        allocation.quota_cost_usd_per_month = cv
        # FR-008: cost-cap changes are audited (the only quota change with an audit
        # event; token-cap edits historically have none).
        await audit.record(
            session,
            event_type=AuditEventType.allocation_cost_quota_updated,
            actor_type=ActorType.admin,
            target_type="allocation",
            target_id=allocation.id,
            details={"quota_cost_usd_per_month": str(cv) if cv is not None else None},
        )
    if "is_service_allocation" in payload:
        allocation.is_service_allocation = bool(payload["is_service_allocation"])
    if "note" in payload:
        allocation.note = payload["note"]
    await session.flush()
    return _to_out(allocation)


class BulkAllocationActionRequest(BaseModel):
    allocation_ids: list[str]
    action: str  # pause | resume | revoke | unquarantine


class BulkAllocationQuotaRequest(BaseModel):
    allocation_ids: list[str]
    quota_tokens_per_month: int | None = None
    quota_cost_usd_per_month: Decimal | None = None


@router.post("/allocations/bulk-action")
async def bulk_allocation_action(payload: BulkAllocationActionRequest) -> dict[str, Any]:
    """Batch pause / resume / revoke / unquarantine. Per-item independent
    transaction — one failure never blocks the rest; each item reports its
    outcome (changed / skipped-with-reason / failed)."""
    valid = {"pause", "resume", "revoke", "unquarantine"}
    if payload.action not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": f"action must be one of {sorted(valid)}"}},
        )
    if not payload.allocation_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "allocation_ids must not be empty"}},
        )
    from ai_api.db import get_sessionmaker
    from ai_api.services.allocations import InvalidAllocationState

    sm = get_sessionmaker()
    results: list[dict[str, Any]] = []
    changed = failed = 0
    for aid in payload.allocation_ids:
        reason: str | None = None
        try:
            async with sm() as s:
                svc = AllocationService(s)
                if payload.action == "unquarantine":
                    a = await svc.get(aid)
                    if a is None:
                        reason = "not_found"
                    elif a.status != AllocationStatus.quarantined:
                        reason = "not_quarantined"
                    else:
                        a.status = AllocationStatus.active
                        await audit.record(
                            s, event_type=AuditEventType.allocation_unquarantined,
                            actor_type=ActorType.admin, target_type="allocation", target_id=a.id,
                        )
                        await s.commit()
                        results.append({"allocation_id": aid, "status": "changed", "reason": None})
                        changed += 1
                        continue
                else:
                    if payload.action == "pause":
                        a = await svc.pause(aid)
                    elif payload.action == "resume":
                        a = await svc.resume(aid)
                    else:  # revoke
                        a = await svc.revoke(aid)
                    if a is None:
                        reason = "not_found"
                    else:
                        await s.commit()
                        results.append({"allocation_id": aid, "status": "changed", "reason": None})
                        changed += 1
                        continue
        except InvalidAllocationState:
            reason = "invalid_state"
        except Exception:
            reason = "internal"
        results.append({"allocation_id": aid, "status": "failed", "reason": reason})
        failed += 1
    return {"changed": changed, "failed": failed, "results": results}


@router.post("/allocations/bulk-quota")
async def bulk_allocation_quota(payload: BulkAllocationQuotaRequest) -> dict[str, Any]:
    """Batch-set monthly quota (tokens and/or USD cost cap) across allocations.
    Pass a value to set it; omit a field to leave it unchanged on each item."""
    if not payload.allocation_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "allocation_ids must not be empty"}},
        )
    fields = payload.model_dump(exclude_unset=True)
    set_tokens = "quota_tokens_per_month" in fields
    set_cost = "quota_cost_usd_per_month" in fields
    if not set_tokens and not set_cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request",
                              "message": "provide quota_tokens_per_month and/or quota_cost_usd_per_month"}},
        )
    if set_tokens and payload.quota_tokens_per_month is not None and payload.quota_tokens_per_month < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "quota_tokens_per_month must be >= 0 or null"}},
        )
    if set_cost and payload.quota_cost_usd_per_month is not None and payload.quota_cost_usd_per_month < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "quota_cost_usd_per_month must be >= 0 or null"}},
        )
    from ai_api.db import get_sessionmaker

    sm = get_sessionmaker()
    results: list[dict[str, Any]] = []
    changed = failed = 0
    for aid in payload.allocation_ids:
        try:
            async with sm() as s:
                a = await AllocationService(s).get(aid)
                if a is None:
                    results.append({"allocation_id": aid, "status": "failed", "reason": "not_found"})
                    failed += 1
                    continue
                if set_tokens:
                    a.quota_tokens_per_month = payload.quota_tokens_per_month
                if set_cost:
                    a.quota_cost_usd_per_month = payload.quota_cost_usd_per_month
                    await audit.record(
                        s, event_type=AuditEventType.allocation_cost_quota_updated,
                        actor_type=ActorType.admin, target_type="allocation", target_id=a.id,
                        details={"quota_cost_usd_per_month":
                                 str(payload.quota_cost_usd_per_month) if payload.quota_cost_usd_per_month is not None else None},
                    )
                await s.commit()
            results.append({"allocation_id": aid, "status": "changed", "reason": None})
            changed += 1
        except Exception:
            results.append({"allocation_id": aid, "status": "failed", "reason": "internal"})
            failed += 1
    return {"changed": changed, "failed": failed, "results": results}


# ---- Phase 18: per-device credentials (admin view) ----


def _cred_out(c: Any) -> CredentialOut:
    return CredentialOut(
        id=c.id,
        name=c.name,
        token_prefix=c.token_prefix,
        created_at=c.created_at,
        last_used_at=c.last_used_at,
        status="revoked" if c.revoked_at else "active",
    )


@router.get(
    "/allocations/{allocation_id}/credentials",
    response_model=list[CredentialOut],
)
async def admin_list_credentials(
    allocation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[CredentialOut]:
    """List every per-device credential of an allocation (no plaintext)."""
    service = AllocationService(session)
    allocation = await service.get(allocation_id)
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    creds = await service.list_credentials(allocation_id)
    return [_cred_out(c) for c in creds]


@router.delete(
    "/allocations/{allocation_id}/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_revoke_credential(
    allocation_id: str,
    credential_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Revoke a single credential (soft) and write an audit record. Other
    credentials of the allocation are unaffected."""
    from ai_api.auth import audit
    from ai_api.models import ActorType, AuditEventType

    service = AllocationService(session)
    credential = await service.get_credential(credential_id)
    if credential is None or not await service.credential_in_allocation_scope(
        credential_id, allocation_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "credential not found"}},
        )
    await service.revoke_credential(credential_id)
    await audit.record(
        session,
        event_type=AuditEventType.credential_revoked,
        actor_type=ActorType.admin,
        target_type="credential",
        target_id=credential_id,
        details={"allocation_id": allocation_id},
    )
    await session.flush()
