"""Phase 5.1: admin diagnostic endpoints — visibility evaluation.

Pure read; no audit. Backs the "為何 X 看不到 Y" UX.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.models import (
    Member,
    MemberStatus,
    MemberTag,
    ModelCatalog,
    ProviderCredential,
    ProviderCredentialStatus,
)
from ai_api.services.model_access import evaluate_visibility

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


async def _active_providers(session: AsyncSession) -> set[str]:
    q = await session.execute(
        select(ProviderCredential.provider).where(
            ProviderCredential.status == ProviderCredentialStatus.active
        ).distinct()
    )
    return set(q.scalars().all())


async def _member_tags(session: AsyncSession, member_id: str) -> set[str]:
    q = await session.execute(
        select(MemberTag.tag).where(MemberTag.member_id == member_id)
    )
    return set(q.scalars().all())


@router.get("/diagnose/visibility")
async def diagnose_visibility(
    member_id: str = Query(...),
    model_slug: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "member not found"))
    model = await session.get(ModelCatalog, model_slug)
    if model is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))

    tags = await _member_tags(session, member_id)
    providers = await _active_providers(session)
    return evaluate_visibility(model, member_tags=tags, active_providers=providers)


@router.get("/members/{member_id}/visible-models")
async def list_visible_models(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "member not found"))
    if member.status != MemberStatus.active:
        # disabled members see nothing
        return []

    tags = await _member_tags(session, member_id)
    providers = await _active_providers(session)
    models_q = await session.execute(
        select(ModelCatalog).order_by(ModelCatalog.slug)
    )
    out: list[dict[str, Any]] = []
    for m in models_q.scalars().all():
        if evaluate_visibility(m, member_tags=tags, active_providers=providers)["visible"]:
            out.append({
                "slug": m.slug,
                "display_name": m.display_name,
                "provider": m.provider,
            })
    return out
