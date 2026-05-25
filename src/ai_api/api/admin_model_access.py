"""Phase 5 US3: admin endpoint to set a model's access policy.

Contract: specs/012-multi-provider-access/contracts/model-access.yaml
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.auth.audit import record as audit_record
from ai_api.models import ActorType, AuditEventType, DefaultAccess, ModelCatalog
from ai_api.services.member_tags import validate_tag

router = APIRouter(dependencies=[Depends(require_admin_token)])


class AccessPolicyUpdate(BaseModel):
    default_access: DefaultAccess | None = None
    allowed_tags: list[str] | None = Field(default=None)
    denied_tags: list[str] | None = Field(default=None)


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _snapshot(m: ModelCatalog) -> dict[str, Any]:
    return {
        "slug": m.slug,
        "default_access": m.default_access.value,
        "allowed_tags": list(m.allowed_tags or []),
        "denied_tags": list(m.denied_tags or []),
    }


@router.patch("/catalog/models/{slug:path}/access")
async def patch_model_access(
    slug: str,
    payload: AccessPolicyUpdate = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))
    if payload.default_access is not None:
        m.default_access = payload.default_access
    if payload.allowed_tags is not None:
        try:
            for t in payload.allowed_tags:
                validate_tag(t)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=_err("invalid_tag", str(exc))
            ) from exc
        m.allowed_tags = list(payload.allowed_tags)
    if payload.denied_tags is not None:
        try:
            for t in payload.denied_tags:
                validate_tag(t)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=_err("invalid_tag", str(exc))
            ) from exc
        m.denied_tags = list(payload.denied_tags)
    await session.flush()
    await audit_record(
        session,
        event_type=AuditEventType.model_access_policy_updated,
        actor_type=ActorType.admin,
        target_type="model_catalog",
        target_id=slug,
        details=_snapshot(m),
    )
    return _snapshot(m)
