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
from ai_api.services import litellm_registry, pricing

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _build_litellm_sync(payload: ModelCatalogCreate) -> dict[str, Any] | None:
    """Derive LiteLLM provenance from the create payload: pick the registry key
    (explicit base_model_key, else slug if it's a registry key), then mark each
    syncable field litellm/borrowed (matches registry) or manual (admin edited).
    Returns None when the model has no LiteLLM counterpart (pure hand-entry)."""
    key = payload.base_model_key or (payload.slug if litellm_registry.lookup(payload.slug) else None)
    if key is None:
        return None
    meta = litellm_registry.lookup(key)
    if meta is None:
        return None
    borrowed = bool(payload.base_model_key) and payload.base_model_key != payload.slug
    matched_source = "borrowed" if borrowed else "litellm"
    field_sources: dict[str, str] = {}
    for field in litellm_registry.SYNCABLE_FIELDS:
        field_sources[field] = matched_source if getattr(payload, field) == meta[field] else "manual"
    return {
        "base_model_key": key,
        "imported_version": litellm_registry.current_version(),
        "field_sources": field_sources,
        "snapshot": meta,
    }


class SuggestedPrice(BaseModel):
    input_per_1k: str
    output_per_1k: str
    cached_input_per_1k: str | None = None


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
    # Phase 23: align with a LiteLLM registry key. If set (or if `slug` itself is a
    # registry key), the backend derives field-source provenance + snapshot.
    base_model_key: str | None = None
    # Optional suggested price to seed (appended as a price version with litellm source_note).
    suggested_price: SuggestedPrice | None = None


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


def _to_dict(m: ModelCatalog, price: dict[str, str] | None = None) -> dict[str, Any]:
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
        "self_service_enabled": m.self_service_enabled,
        "self_service_default_quota": m.self_service_default_quota,
        "litellm_sync": m.litellm_sync,  # Phase 23 provenance or null
        "price": price,  # current per-1K {input_per_1k, output_per_1k} or null
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

    price_map = await pricing.current_price_map(session, datetime.now(UTC))
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
        body = _to_dict(m, pricing.price_for_slug(price_map, m.provider, m.slug))
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


@router.get("/catalog/litellm/search")
async def admin_litellm_search(q: str = "", limit: int = 20) -> dict[str, Any]:
    """Phase 23: search LiteLLM's bundled registry for the create-time picker."""
    return {"results": litellm_registry.search(q, min(max(limit, 1), 50))}


@router.get("/catalog/litellm/suggest/{key:path}")
async def admin_litellm_suggest(key: str) -> dict[str, Any]:
    """Phase 23: bring-in draft (metadata + suggested price) for one registry key."""
    meta = litellm_registry.lookup(key)
    if meta is None:
        raise HTTPException(
            status_code=404,
            detail=_err("litellm_model_not_found", f"LiteLLM has no model {key!r}"),
        )
    return {
        "key": key,
        "slug_default": key,
        "metadata": meta,
        "suggested_price": litellm_registry.suggest_price(key),
        "imported_version": litellm_registry.current_version(),
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
        litellm_sync=_build_litellm_sync(payload),
        created_at=now,
        updated_at=now,
    )
    session.add(m)
    await session.flush()
    # Phase 23: seed the suggested price as a versioned row (litellm = suggestion;
    # our price_list stays the billing source of truth).
    if payload.suggested_price is not None:
        await pricing.create_version(
            session,
            provider=payload.provider,
            model=payload.slug.split("/", 1)[-1],
            input_per_1k=payload.suggested_price.input_per_1k,
            output_per_1k=payload.suggested_price.output_per_1k,
            cached_input_per_1k=payload.suggested_price.cached_input_per_1k,
            effective_from=now,
            source_note=f"litellm@{litellm_registry.current_version()}",
        )
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
    touched_syncable: list[str] = []
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
        changed = True
        if field in litellm_registry.SYNCABLE_FIELDS:
            touched_syncable.append(field)
    # Phase 23: editing a synced field flips its source to manual (snapshot kept).
    if touched_syncable and m.litellm_sync:
        sync = dict(m.litellm_sync)  # reassign so SQLAlchemy detects the JSON change
        sources = dict(sync.get("field_sources", {}))
        for field in touched_syncable:
            sources[field] = "manual"
        sync["field_sources"] = sources
        m.litellm_sync = sync
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


class LitellmApply(BaseModel):
    fields: list[str]
    litellm_version: str | None = None


def _price_diffs(
    current: dict[str, str] | None, latest: dict[str, str | None] | None
) -> list[dict[str, Any]]:
    from decimal import Decimal

    diffs: list[dict[str, Any]] = []
    for pf in ("input_per_1k", "output_per_1k", "cached_input_per_1k"):
        new_v = (latest or {}).get(pf)
        if new_v is None:
            continue
        cur_v = (current or {}).get(pf)
        changed = cur_v is None or Decimal(str(cur_v)) != Decimal(str(new_v))
        diffs.append(
            {"field": f"price.{pf}", "current": cur_v, "latest": new_v, "source": "litellm", "changed": changed}
        )
    return diffs


@router.post("/catalog/models/{slug:path}/litellm-check")
async def admin_litellm_check(
    slug: str, session: AsyncSession = Depends(get_db_session)
) -> dict[str, Any]:
    """Phase 23: fetch the latest registry (timeout → bundled fallback) and diff
    each syncable field + price against the model's current values."""
    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))
    key = (m.litellm_sync or {}).get("base_model_key") or slug
    latest_map = await litellm_registry.fetch_latest()
    source = "live"
    if latest_map is None:
        latest_map, source = litellm_registry.bundled(), "bundled-fallback"
    entry = latest_map.get(key)
    sources = (m.litellm_sync or {}).get("field_sources", {})
    diffs: list[dict[str, Any]] = []
    if entry is not None:
        latest_meta = litellm_registry.metadata_from_entry(entry)
        for field in litellm_registry.SYNCABLE_FIELDS:
            cur = getattr(m, field)
            new = latest_meta[field]
            diffs.append(
                {"field": field, "current": cur, "latest": new,
                 "source": sources.get(field, "manual"), "changed": cur != new}
            )
        cur_price = pricing.price_for_slug(
            await pricing.current_price_map(session, datetime.now(UTC)), m.provider, slug
        )
        diffs += _price_diffs(cur_price, litellm_registry.price_from_entry(entry))
    return {
        "source": source,
        "litellm_version": litellm_registry.current_version(),
        "base_model_key": key,
        "diffs": diffs,
    }


@router.post("/catalog/models/{slug:path}/litellm-apply")
async def admin_litellm_apply(
    slug: str,
    payload: LitellmApply = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Phase 23: apply selected, non-manual fields. Metadata fields update the
    catalog + snapshot; price fields append a new price version (never overwrite)."""
    m = await session.get(ModelCatalog, slug)
    if m is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "model not found"))
    key = (m.litellm_sync or {}).get("base_model_key") or slug
    latest_map = await litellm_registry.fetch_latest() or litellm_registry.bundled()
    entry = latest_map.get(key)
    if entry is None:
        raise HTTPException(
            status_code=422,
            detail=_err("litellm_model_not_found", f"LiteLLM has no model {key!r}"),
        )
    latest_meta = litellm_registry.metadata_from_entry(entry)
    sources = (m.litellm_sync or {}).get("field_sources", {})
    applied_meta: list[str] = []
    want_price = False
    for field in payload.fields:
        if field in litellm_registry.SYNCABLE_FIELDS:
            if sources.get(field) == "manual":
                continue  # never auto-overwrite a manual field
            setattr(m, field, latest_meta[field])
            applied_meta.append(field)
        elif field.startswith("price."):
            want_price = True
    if applied_meta and m.litellm_sync:
        sync = dict(m.litellm_sync)
        fs, snap = dict(sync.get("field_sources", {})), dict(sync.get("snapshot", {}))
        for field in applied_meta:
            fs[field], snap[field] = "litellm", latest_meta[field]
        sync["field_sources"], sync["snapshot"] = fs, snap
        sync["imported_version"] = litellm_registry.current_version()
        m.litellm_sync = sync
    if want_price:
        lp = litellm_registry.price_from_entry(entry) or {}
        inp = lp.get("input_per_1k")
        if inp is not None:
            await pricing.create_version(
                session,
                provider=m.provider,
                model=slug.split("/", 1)[-1],
                input_per_1k=inp,
                output_per_1k=lp.get("output_per_1k") or "0",
                cached_input_per_1k=lp.get("cached_input_per_1k"),
                effective_from=datetime.now(UTC),
                source_note=f"litellm@{litellm_registry.current_version()}",
            )
    if applied_meta or want_price:
        m.updated_at = datetime.now(UTC)
        await session.flush()
        await audit_record(
            session,
            event_type=AuditEventType.model_access_policy_updated,
            actor_type=ActorType.admin,
            target_type="model_catalog",
            target_id=slug,
            details={"action": "litellm_apply", "fields": payload.fields},
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
