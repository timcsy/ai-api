"""Phase 6 / US1 + US3: admin self-service configuration.

- PATCH /admin/catalog/models/{slug}/self-service — open/close + default quota
- GET   /admin/self-service-locks               — list reclaim locks
- POST  /admin/self-service-locks/unlock         — clear a (member, model) lock

Contract: specs/015-self-service-allocation/contracts/admin-self-service.yaml
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.auth.audit import record as audit_record
from ai_api.models import (
    ActorType,
    AuditEventType,
    Member,
    ModelCatalog,
    SelfServiceReclaimLock,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


class SelfServiceUpdate(BaseModel):
    enabled: bool
    default_quota: int | None = None


def _config(m: ModelCatalog) -> dict[str, Any]:
    return {
        "slug": m.slug,
        "self_service_enabled": m.self_service_enabled,
        "self_service_default_quota": m.self_service_default_quota,
    }


@router.patch("/catalog/models/{slug:path}/self-service")
async def patch_self_service(
    slug: str,
    payload: SelfServiceUpdate = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))
    if payload.enabled:
        if payload.default_quota is None or payload.default_quota <= 0:
            raise HTTPException(
                status_code=422,
                detail=_err("quota_required", "default_quota (>0) required when enabling self-service"),
            )
        m.self_service_enabled = True
        m.self_service_default_quota = payload.default_quota
    else:
        m.self_service_enabled = False
        # keep the stored quota so re-enabling pre-fills; not required
    await session.flush()
    await audit_record(
        session,
        event_type=AuditEventType.model_access_policy_updated,
        actor_type=ActorType.admin,
        actor_id=None,
        target_type="model",
        target_id=slug,
        details={"self_service": _config(m)},
    )
    return _config(m)


@router.get("/self-service-locks")
async def list_locks(session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    rows = (await session.execute(select(SelfServiceReclaimLock))).scalars().all()
    if not rows:
        return []
    members = {
        m.id: m.email
        for m in (
            await session.execute(
                select(Member).where(Member.id.in_([r.member_id for r in rows]))
            )
        ).scalars().all()
    }
    return [
        {
            "member_id": r.member_id,
            "member_email": members.get(r.member_id),
            "model_slug": r.model_slug,
            "locked_at": r.locked_at.isoformat(),
            "locked_by": r.locked_by,
        }
        for r in rows
    ]


class UnlockRequest(BaseModel):
    member_id: str
    model_slug: str


@router.post("/self-service-locks/unlock", status_code=status.HTTP_204_NO_CONTENT)
async def unlock(
    payload: UnlockRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    result = await session.execute(
        delete(SelfServiceReclaimLock).where(
            SelfServiceReclaimLock.member_id == payload.member_id,
            SelfServiceReclaimLock.model_slug == payload.model_slug,
        )
    )
    if (getattr(result, "rowcount", 0) or 0) > 0:
        await audit_record(
            session,
            event_type=AuditEventType.self_service_unlocked,
            actor_type=ActorType.admin,
            actor_id=None,
            target_type="member",
            target_id=payload.member_id,
            details={"model": payload.model_slug},
        )
