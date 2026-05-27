"""Phase 6: self-service allocation — eligibility + claim + claimable list.

Eligibility reuses `evaluate_visibility` (credential gate ∩ access policy) and
adds three self-service-specific gates (opt-in flag, one-active-per-model,
reclaim lock). The claim path delegates issuance to `AllocationService.create`
so self-service allocations are byte-for-byte equivalent to admin-created ones.
"""
from __future__ import annotations

from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai_api.auth.audit import record as audit_record
from ai_api.models import (
    ActorType,
    Allocation,
    AllocationOrigin,
    AllocationStatus,
    AuditEventType,
    Member,
    MemberStatus,
    MemberTag,
    ModelCatalog,
    ProviderCredential,
    ProviderCredentialStatus,
    SelfServiceReclaimLock,
)
from ai_api.services.allocations import AllocationCreated, AllocationService
from ai_api.services.model_access import evaluate_visibility


class ClaimEligibility(TypedDict):
    eligible: bool
    reason: str | None  # member_inactive / model_not_self_service / model_forbidden / already_claimed / reclaim_locked


def evaluate_claim_eligibility(
    *,
    member_active: bool,
    model: Any,
    member_tags: set[str],
    active_providers: set[str],
    has_active_self_alloc: bool,
    reclaim_locked: bool,
) -> ClaimEligibility:
    """Pure first-fail ordering: structural blocks before state blocks."""
    if not member_active:
        return {"eligible": False, "reason": "member_inactive"}
    if not model.self_service_enabled:
        return {"eligible": False, "reason": "model_not_self_service"}
    if not evaluate_visibility(model, member_tags, active_providers)["visible"]:
        return {"eligible": False, "reason": "model_forbidden"}
    if has_active_self_alloc:
        return {"eligible": False, "reason": "already_claimed"}
    if reclaim_locked:
        return {"eligible": False, "reason": "reclaim_locked"}
    return {"eligible": True, "reason": None}


class ClaimError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SelfServiceService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _active_providers(self) -> set[str]:
        stmt = select(ProviderCredential.provider).where(
            ProviderCredential.status == ProviderCredentialStatus.active
        )
        return set((await self._s.execute(stmt)).scalars().all())

    async def _member_tags(self, member_id: str) -> set[str]:
        stmt = select(MemberTag.tag).where(MemberTag.member_id == member_id)
        return set((await self._s.execute(stmt)).scalars().all())

    async def _has_active_self_alloc(self, member_id: str, slug: str) -> bool:
        stmt = select(Allocation.id).where(
            Allocation.member_id == member_id,
            Allocation.resource_model == slug,
            Allocation.origin == AllocationOrigin.self_service,
            Allocation.status == AllocationStatus.active,
        )
        return (await self._s.execute(stmt)).first() is not None

    async def _is_locked(self, member_id: str, slug: str) -> bool:
        return (
            await self._s.get(SelfServiceReclaimLock, (member_id, slug))
        ) is not None

    async def check(self, member: Member, slug: str) -> tuple[ClaimEligibility, ModelCatalog | None]:
        model = await self._s.get(ModelCatalog, slug)
        if model is None:
            return {"eligible": False, "reason": "not_found"}, None
        elig = evaluate_claim_eligibility(
            member_active=member.status == MemberStatus.active,
            model=model,
            member_tags=await self._member_tags(member.id),
            active_providers=await self._active_providers(),
            has_active_self_alloc=await self._has_active_self_alloc(member.id, slug),
            reclaim_locked=await self._is_locked(member.id, slug),
        )
        return elig, model

    async def claim(self, member: Member, slug: str) -> AllocationCreated:
        elig, model = await self.check(member, slug)
        if not elig["eligible"] or model is None:
            raise ClaimError(elig["reason"] or "not_found")
        created = await AllocationService(self._s).create(
            member_id=member.id,
            resource_model=slug,
            quota_tokens_per_month=model.self_service_default_quota,
            origin=AllocationOrigin.self_service,
            created_by=f"self-service:{member.id}",
        )
        await audit_record(
            self._s,
            event_type=AuditEventType.self_service_claimed,
            actor_type=ActorType.member,
            actor_id=member.id,
            target_type="model",
            target_id=slug,
            details={
                "allocation_id": created.allocation.id,
                "quota": model.self_service_default_quota,
            },
        )
        return created

    async def existing_active(self, member_id: str, slug: str) -> Allocation | None:
        stmt = select(Allocation).options(selectinload(Allocation.credential)).where(
            Allocation.member_id == member_id,
            Allocation.resource_model == slug,
            Allocation.origin == AllocationOrigin.self_service,
            Allocation.status == AllocationStatus.active,
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def list_claimable(self, member: Member) -> list[dict[str, Any]]:
        """Models opened for self-service AND visible to this member, with
        per-model claim state (already_claimed / reclaim_locked / claimable)."""
        if member.status != MemberStatus.active:
            return []
        tags = await self._member_tags(member.id)
        providers = await self._active_providers()
        # Models the member can ALREADY use (any active allocation, admin or
        # self-service) — don't offer to self-claim what they already hold.
        held = set(
            (
                await self._s.execute(
                    select(Allocation.resource_model).where(
                        Allocation.member_id == member.id,
                        Allocation.status == AllocationStatus.active,
                    )
                )
            ).scalars().all()
        )
        models = (
            await self._s.execute(
                select(ModelCatalog).where(ModelCatalog.self_service_enabled.is_(True))
            )
        ).scalars().all()
        out: list[dict[str, Any]] = []
        for m in models:
            if not evaluate_visibility(m, tags, providers)["visible"]:
                continue
            if m.slug in held:
                continue  # already has a usable allocation for this model
            state = "reclaim_locked" if await self._is_locked(member.id, m.slug) else "claimable"
            out.append({
                "slug": m.slug,
                "display_name": m.display_name,
                "provider": m.provider,
                "default_quota": m.self_service_default_quota,
                "state": state,
            })
        return out
