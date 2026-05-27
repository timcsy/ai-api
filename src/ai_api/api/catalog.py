"""Catalog endpoints (Phase 4): list / detail / filters.

All endpoints require an active member.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_active_member
from ai_api.models import Member, ModelCatalog
from ai_api.services import pricing
from ai_api.services.model_access import ModelAccessService
from ai_api.services.model_catalog import compute_facets, filter_models

router = APIRouter(dependencies=[Depends(require_active_member)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _to_summary(m: ModelCatalog, price: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "slug": m.slug,
        "provider": m.provider,
        "display_name": m.display_name,
        "family": m.family,
        "description": m.description,
        "modality_input": list(m.modality_input),
        "modality_output": list(m.modality_output),
        "capabilities": list(m.capabilities),
        "context_window": m.context_window,
        "cost_tier": m.cost_tier,
        "recommended_for": list(m.recommended_for),
        "tags": list(m.tags),
        "official_doc_url": m.official_doc_url,
        "status": m.status,
        "price": price,  # current per-1K {input_per_1k, output_per_1k} or null
    }


def _to_detail(m: ModelCatalog, price: dict[str, str] | None = None) -> dict[str, Any]:
    out = _to_summary(m, price)
    out["example_request"] = m.example_request
    out["deprecation_note"] = m.deprecation_note
    out["created_at"] = m.created_at.isoformat()
    out["updated_at"] = m.updated_at.isoformat()
    return out


@router.get("/models")
async def list_models(
    capability: list[str] | None = Query(default=None),
    modality_input: list[str] | None = Query(default=None),
    modality_output: list[str] | None = Query(default=None),
    recommended_for: list[str] | None = Query(default=None),
    tag: list[str] | None = Query(default=None),
    cost_tier: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    family: str | None = Query(default=None),
    min_context_window: int | None = Query(default=None, ge=0),
    include_deprecated: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
    member: Member = Depends(require_active_member),
) -> list[dict[str, Any]]:
    stmt = select(ModelCatalog).order_by(ModelCatalog.slug)
    if not include_deprecated:
        stmt = stmt.where(ModelCatalog.status != "deprecated")
    models = list((await session.execute(stmt)).scalars().all())
    # Phase 5: apply two-stage filter (credential gate ∩ access policy)
    visible = await ModelAccessService(session).visible_to_member(member, models)
    filtered = filter_models(
        visible,
        capabilities=capability,
        modality_input=modality_input,
        modality_output=modality_output,
        recommended_for=recommended_for,
        tags=tag,
        cost_tier=cost_tier,
        provider=provider,
        family=family,
        min_context_window=min_context_window,
    )
    price_map = await pricing.current_price_map(session, datetime.now(UTC))
    return [
        _to_summary(m, pricing.price_for_slug(price_map, m.provider, m.slug))
        for m in filtered
    ]


@router.get("/models/{slug:path}")
async def get_model(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
    member: Member = Depends(require_active_member),
) -> dict[str, Any]:
    model = (
        await session.execute(
            select(ModelCatalog).where(ModelCatalog.slug == slug)
        )
    ).scalar_one_or_none()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_err("not_found", f"model {slug} not found"),
        )
    # Phase 5: filter — return 404 (not 403) on policy deny to avoid leaking existence
    if not await ModelAccessService(session).is_accessible(member, model):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_err("not_found", f"model {slug} not found"),
        )
    price_map = await pricing.current_price_map(session, datetime.now(UTC))
    return _to_detail(model, pricing.price_for_slug(price_map, model.provider, model.slug))


@router.get("/filters")
async def get_filters(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, dict[str, int]]:
    stmt = (
        select(ModelCatalog)
        .where(ModelCatalog.status != "deprecated")
        .order_by(ModelCatalog.slug)
    )
    models = list((await session.execute(stmt)).scalars().all())
    return compute_facets(models)
