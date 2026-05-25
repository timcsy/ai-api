"""Phase 5: model access policy — two-stage filtering (credential gate ∩ access policy).

Used by:
- catalog list/detail endpoints to filter what each member can see
- proxy router as defensive secondary check before upstream call
"""
from __future__ import annotations

from typing import Any

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


def evaluate_visibility(
    model: Any, member_tags: set[str], active_providers: set[str]
) -> dict[str, Any]:
    """Phase 5.1 — pure function returning {visible, reason_chain}.

    Pure function (works with ORM rows or SimpleNamespace) so it's testable
    without a DB. `model` only needs `.provider`, `.default_access`,
    `.allowed_tags`, `.denied_tags`. Short-circuits on first failure.
    """
    chain: list[dict[str, Any]] = []
    # 1. Credential gate
    has_cred = model.provider in active_providers
    chain.append({
        "check": "credential_gate",
        "pass": has_cred,
        "detail": (
            f"provider {model.provider!r} has at least 1 active credential"
            if has_cred
            else f"no active credential for provider {model.provider!r}"
        ),
    })
    if not has_cred:
        return {"visible": False, "reason_chain": chain}

    # 2. Default access (informational, not pass/fail)
    chain.append({
        "check": "default_access",
        "pass": True,
        "detail": f"default_access = {model.default_access.value if hasattr(model.default_access, 'value') else model.default_access}",
    })

    # 3. Deny tags (deny wins)
    denied = set(model.denied_tags or [])
    deny_hits = denied & member_tags
    chain.append({
        "check": "deny_tags",
        "pass": not deny_hits,
        "detail": (
            f"member tags ∩ denied = {sorted(deny_hits)} → blocked"
            if deny_hits
            else "member tags ∩ denied = ∅"
        ),
    })
    if deny_hits:
        return {"visible": False, "reason_chain": chain}

    # 4. Allow tags (only matters if restricted)
    da = model.default_access
    da_val = da.value if hasattr(da, "value") else da
    if da_val == "open":
        return {"visible": True, "reason_chain": chain}

    allowed = set(model.allowed_tags or [])
    allow_hits = allowed & member_tags
    chain.append({
        "check": "allow_tags",
        "pass": bool(allow_hits),
        "detail": (
            f"member tags {sorted(member_tags)} ∩ allowed {sorted(allowed)} = {sorted(allow_hits)}"
            if allow_hits
            else f"member tags {sorted(member_tags)} ∩ allowed {sorted(allowed)} = ∅ → blocked"
        ),
    })
    return {"visible": bool(allow_hits), "reason_chain": chain}


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
