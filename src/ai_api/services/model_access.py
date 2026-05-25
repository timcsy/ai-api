"""Phase 5: model access policy — two-stage filtering (credential gate ∩ access policy).

Used by:
- catalog list/detail endpoints to filter what each member can see
- proxy router as defensive secondary check before upstream call
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import (
    DefaultAccess,
    Member,
    MemberTag,
    ModelCatalog,
    ProviderCredential,
    ProviderCredentialStatus,
)


def access_policy_allows(model: ModelCatalog, member_tags: set[str]) -> bool:
    """Pure-function: given a model and member's tag set, return True iff policy permits.

    Logic:
    - Deny overrides everything: if any denied_tag intersects member_tags → False
    - default_access == open → True (subject to deny above)
    - default_access == restricted → True iff any allowed_tag intersects member_tags
    """
    denied = set(model.denied_tags or [])
    if denied & member_tags:
        return False
    if model.default_access == DefaultAccess.open:
        return True
    allowed = set(model.allowed_tags or [])
    return bool(allowed & member_tags)


class ModelAccessService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_member_tags(self, member_id: str) -> set[str]:
        stmt = select(MemberTag.tag).where(MemberTag.member_id == member_id)
        return set((await self._s.execute(stmt)).scalars().all())

    async def get_providers_with_active_credentials(self) -> set[str]:
        stmt = select(ProviderCredential.provider).where(
            ProviderCredential.status == ProviderCredentialStatus.active
        ).distinct()
        return set((await self._s.execute(stmt)).scalars().all())

    async def visible_to_member(
        self, member: Member, models: list[ModelCatalog]
    ) -> list[ModelCatalog]:
        """Filter `models` to those this member can see (credential gate ∩ access policy)."""
        tags = await self.get_member_tags(member.id)
        active_providers = await self.get_providers_with_active_credentials()
        return [
            m
            for m in models
            if m.provider in active_providers and access_policy_allows(m, tags)
        ]

    async def is_accessible(self, member: Member, model: ModelCatalog) -> bool:
        """Proxy-time defensive check for a single model."""
        active = await self.get_providers_with_active_credentials()
        if model.provider not in active:
            return False
        tags = await self.get_member_tags(member.id)
        return access_policy_allows(model, tags)
