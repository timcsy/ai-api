"""Phase 5+: admin endpoints for managing the model catalog itself.

This complements `/admin/catalog/models/{slug}/access` (access policy patch).
Here admin can list (unfiltered) / create / update / delete catalog entries.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.auth.audit import record as audit_record
from ai_api.config import get_settings
from ai_api.models import ActorType, AuditEventType, DefaultAccess, ModelCatalog

router = APIRouter(dependencies=[Depends(require_admin_token)])


class ModelCatalogCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+/[a-z0-9.-]+$")
    provider: str
    display_name: str
    family: str = "general"
    description: str = ""
    modality_input: list[str] = Field(default_factory=lambda: ["text"])
    modality_output: list[str] = Field(default_factory=lambda: ["text"])
    capabilities: list[str] = Field(default_factory=lambda: ["chat"])
    context_window: int = Field(default=4096, ge=0)
    cost_tier: str = "medium"
    recommended_for: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    example_request: dict[str, Any] = Field(default_factory=dict)
    official_doc_url: str | None = None
    status: str = "active"
    default_access: DefaultAccess = DefaultAccess.open
    allowed_tags: list[str] = Field(default_factory=list)
    denied_tags: list[str] = Field(default_factory=list)


class ModelCatalogUpdate(BaseModel):
    display_name: str | None = None
    family: str | None = None
    description: str | None = None
    modality_input: list[str] | None = None
    modality_output: list[str] | None = None
    capabilities: list[str] | None = None
    context_window: int | None = None
    cost_tier: str | None = None
    recommended_for: list[str] | None = None
    tags: list[str] | None = None
    example_request: dict[str, Any] | None = None
    official_doc_url: str | None = None
    status: str | None = None


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _to_dict(m: ModelCatalog) -> dict[str, Any]:
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
        "deprecation_note": m.deprecation_note,
        "default_access": m.default_access.value,
        "allowed_tags": list(m.allowed_tags or []),
        "denied_tags": list(m.denied_tags or []),
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }


@router.get("/catalog/models")
async def admin_list_models(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Admin sees ALL models (no credential gate / no access policy filter).

    Each row includes `visibility` derived metadata so admin can spot models
    that are hidden from members despite being in the catalog:
      - `provider_has_credential`: any active credential for this provider
      - `visible_member_count`: how many active members can actually see it
        (after both gates: credential + access policy)
    """
    from ai_api.models import (
        Allocation,
        Member,
        MemberStatus,
        MemberTag,
        ProviderCredential,
        ProviderCredentialStatus,
    )
    from ai_api.services.model_access import access_policy_allows

    rows = list((await session.execute(
        select(ModelCatalog).order_by(ModelCatalog.slug)
    )).scalars().all())

    # Which providers currently have an active credential?
    active_providers_q = await session.execute(
        select(ProviderCredential.provider)
        .where(ProviderCredential.status == ProviderCredentialStatus.active)
        .distinct()
    )
    active_providers = set(active_providers_q.scalars().all())

    # All active members + their tag sets (small N for org-internal).
    members_q = await session.execute(
        select(Member).where(Member.status == MemberStatus.active)
    )
    members = list(members_q.scalars().all())
    tags_q = await session.execute(select(MemberTag.member_id, MemberTag.tag))
    tags_by_member: dict[str, set[str]] = {}
    for mid, tag in tags_q.all():
        tags_by_member.setdefault(mid, set()).add(tag)

    # Count allocations bound to each slug (for D — orphan model hint).
    alloc_q = await session.execute(
        select(Allocation.resource_model)
    )
    alloc_counts: dict[str, int] = {}
    for (rm,) in alloc_q.all():
        alloc_counts[rm] = alloc_counts.get(rm, 0) + 1

    out: list[dict[str, Any]] = []
    for m in rows:
        provider_has_cred = m.provider in active_providers
        if not provider_has_cred:
            visible = 0
        else:
            visible = sum(
                1
                for member in members
                if access_policy_allows(m, tags_by_member.get(member.id, set()))
            )
        body = _to_dict(m)
        body["visibility"] = {
            "provider_has_credential": provider_has_cred,
            "visible_member_count": visible,
            "total_active_members": len(members),
            "allocation_count": alloc_counts.get(m.slug, 0),
        }
        out.append(body)
    return out


class AccessPreviewRequest(BaseModel):
    default_access: DefaultAccess
    allowed_tags: list[str] = Field(default_factory=list)
    denied_tags: list[str] = Field(default_factory=list)


@router.post("/catalog/models/{slug:path}/access-preview")
async def admin_preview_access(
    slug: str,
    payload: AccessPreviewRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Preview which active members would see this model under a hypothetical
    policy — without writing changes."""
    from types import SimpleNamespace

    from ai_api.models import (
        Member,
        MemberStatus,
        MemberTag,
        ProviderCredential,
        ProviderCredentialStatus,
    )
    from ai_api.services.model_access import access_policy_allows

    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))

    has_cred_q = await session.execute(
        select(ProviderCredential).where(
            ProviderCredential.provider == m.provider,
            ProviderCredential.status == ProviderCredentialStatus.active,
        ).limit(1)
    )
    provider_has_cred = has_cred_q.scalar_one_or_none() is not None

    members_q = await session.execute(
        select(Member).where(Member.status == MemberStatus.active)
    )
    members = list(members_q.scalars().all())
    tags_q = await session.execute(select(MemberTag.member_id, MemberTag.tag))
    tags_by_member: dict[str, set[str]] = {}
    for mid, tag in tags_q.all():
        tags_by_member.setdefault(mid, set()).add(tag)

    pretend = SimpleNamespace(
        default_access=payload.default_access,
        allowed_tags=payload.allowed_tags,
        denied_tags=payload.denied_tags,
    )
    visible_ids = [
        mb.id
        for mb in members
        if provider_has_cred
        and access_policy_allows(pretend, tags_by_member.get(mb.id, set()))  # type: ignore[arg-type]
    ]
    return {
        "slug": slug,
        "provider_has_credential": provider_has_cred,
        "visible_member_count": len(visible_ids),
        "visible_member_ids": visible_ids[:50],  # cap for payload size
        "total_active_members": len(members),
    }


@router.get("/catalog/models/{slug:path}/dependents")
async def admin_list_dependents(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List allocations bound to this slug — admin sees what will break if model is deleted."""
    from ai_api.models import Allocation
    q = await session.execute(
        select(Allocation).where(Allocation.resource_model == slug)
    )
    allocs = q.scalars().all()
    return {
        "slug": slug,
        "allocation_count": len(allocs),
        "allocations": [
            {
                "id": a.id,
                "member_id": a.member_id,
                "subject_snapshot": a.subject_snapshot,
                "status": a.status.value,
            }
            for a in allocs[:50]
        ],
    }


@router.post(
    "/catalog/models",
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_model(
    payload: ModelCatalogCreate = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    settings = get_settings()
    if payload.provider not in settings.allowed_providers:
        raise HTTPException(
            status_code=422,
            detail=_err(
                "provider_not_allowed",
                f"provider {payload.provider!r} is not in ALLOWED_PROVIDERS",
            ),
        )
    if await session.get(ModelCatalog, payload.slug) is not None:
        raise HTTPException(
            status_code=409,
            detail=_err("duplicate_slug", f"model with slug {payload.slug!r} exists"),
        )
    now = datetime.now(UTC)
    m = ModelCatalog(
        slug=payload.slug,
        provider=payload.provider,
        display_name=payload.display_name,
        family=payload.family,
        description=payload.description,
        modality_input=payload.modality_input,
        modality_output=payload.modality_output,
        capabilities=payload.capabilities,
        context_window=payload.context_window,
        cost_tier=payload.cost_tier,
        recommended_for=payload.recommended_for,
        tags=payload.tags,
        example_request=payload.example_request,
        official_doc_url=payload.official_doc_url,
        status=payload.status,
        deprecation_note=None,
        default_access=payload.default_access,
        allowed_tags=payload.allowed_tags,
        denied_tags=payload.denied_tags,
        created_at=now,
        updated_at=now,
    )
    session.add(m)
    await session.flush()
    await audit_record(
        session,
        event_type=AuditEventType.model_access_policy_updated,
        actor_type=ActorType.admin,
        target_type="model_catalog",
        target_id=payload.slug,
        details={"action": "created", "provider": payload.provider},
    )
    return _to_dict(m)


@router.patch("/catalog/models/{slug:path}")
async def admin_update_model(
    slug: str,
    payload: ModelCatalogUpdate = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))
    changed = False
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
        changed = True
    if changed:
        m.updated_at = datetime.now(UTC)
        await session.flush()
        await audit_record(
            session,
            event_type=AuditEventType.model_access_policy_updated,
            actor_type=ActorType.admin,
            target_type="model_catalog",
            target_id=slug,
            details={"action": "updated"},
        )
    return _to_dict(m)


@router.delete("/catalog/models/{slug:path}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_model(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))
    await session.delete(m)
    await session.flush()
    await audit_record(
        session,
        event_type=AuditEventType.model_access_policy_updated,
        actor_type=ActorType.admin,
        target_type="model_catalog",
        target_id=slug,
        details={"action": "deleted"},
    )
