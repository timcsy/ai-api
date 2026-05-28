"""Phase 11: shared pre-flight pipeline for proxy endpoints.

Both `/v1/chat/completions` and `/v1/responses` run the same authorization /
attribution / quota / binding / access / credential checks before talking to the
upstream. This module centralizes that pipeline so the two endpoints can't drift.

Returns a structured result rather than raising: the caller owns call recording,
and (per the "bind context before raising" lesson) the allocation is bound onto
the rejection so allocation-attributed rejects still record an allocation_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import Allocation
from ai_api.proxy.allowlist import check_allowed, parse_provider
from ai_api.proxy.guard import enforce_model_binding
from ai_api.services.allocations import AllocationService
from ai_api.services.provider_credentials import (
    ProviderCredentialService,
    ProviderUnavailableError,
    ResolvedCredential,
)
from ai_api.services.quota import current_month_usage, is_over_quota


@dataclass
class PreflightSuccess:
    allocation: Allocation
    provider: str
    resolved: ResolvedCredential
    upstream_model: str


@dataclass
class PreflightRejection:
    code: str
    message: str
    http_status: int
    allocation: Allocation | None = None


async def _resolve_credential(
    service: ProviderCredentialService, provider: str, settings: Any
) -> ResolvedCredential:
    """DB-first credential lookup with Azure env fallback for transitional release."""
    cred = await service.get_next(provider)
    if cred is not None:
        return cred
    if provider == "azure" and settings.azure_openai_api_key:
        return ResolvedCredential(
            id="env-fallback",
            provider="azure",
            label="env-fallback",
            api_key=settings.azure_openai_api_key,
            base_url=settings.azure_openai_api_base or None,
            extra_config={"api_version": settings.azure_openai_api_version},
        )
    raise ProviderUnavailableError(provider)


async def run_preflight(
    session: AsyncSession,
    *,
    settings: Any,
    token: str,
    requested_model: str,
) -> PreflightSuccess | PreflightRejection:
    """Run all pre-upstream checks. Returns success context or a rejection."""
    # Provider allowlist (before any DB lookups).
    provider, _ = parse_provider(requested_model)
    if not check_allowed(provider, settings.allowed_providers):
        return PreflightRejection(
            "provider_not_allowed",
            f"provider '{provider}' is not in the allowlist",
            403,
        )

    # Allocation lookup, then bind before status checks so rejects attribute.
    alloc_service = AllocationService(session)
    allocation = await alloc_service.lookup_by_token(token)
    if allocation is None:
        return PreflightRejection("unauthorized", "invalid credential", 401)

    if allocation.status.value == "revoked":
        return PreflightRejection(
            "allocation_revoked", "allocation has been revoked", 403, allocation
        )
    if allocation.status.value == "quarantined":
        return PreflightRejection(
            "allocation_quarantined",
            "allocation is quarantined due to anomalous usage",
            403,
            allocation,
        )
    if allocation.status.value == "paused":
        return PreflightRejection(
            "allocation_paused", "allocation is paused", 403, allocation
        )

    # Monthly quota.
    if allocation.quota_tokens_per_month is not None:
        usage = await current_month_usage(session, allocation.id)
        if is_over_quota(allocation, usage):
            return PreflightRejection(
                "quota_exceeded",
                f"monthly quota reached ({usage}/{allocation.quota_tokens_per_month} tokens)",
                403,
                allocation,
            )

    # Model binding.
    from fastapi import HTTPException

    try:
        enforce_model_binding(allocation, requested_model)
    except HTTPException as exc:
        return PreflightRejection(
            exc.detail["error"]["code"],  # type: ignore[index]
            exc.detail["error"]["message"],  # type: ignore[index]
            exc.status_code,
            allocation,
        )

    # Model access policy (defensive secondary check; catalog filter is primary).
    from ai_api.models import Member as MemberModel
    from ai_api.models import ModelCatalog
    from ai_api.services.model_access import ModelAccessService

    model_row = (
        await session.execute(
            select(ModelCatalog).where(ModelCatalog.slug == requested_model)
        )
    ).scalar_one_or_none()
    if model_row is not None:
        member_row = await session.get(MemberModel, allocation.member_id)
        if member_row is not None and not await ModelAccessService(session).is_accessible(
            member_row, model_row
        ):
            return PreflightRejection(
                "model_forbidden",
                f"model '{requested_model}' is not accessible to this member",
                403,
                allocation,
            )

    # Resolve provider credential.
    cred_service = ProviderCredentialService(session)
    try:
        resolved = await _resolve_credential(cred_service, provider, settings)
    except ProviderUnavailableError:
        return PreflightRejection(
            "provider_unavailable",
            f"no active credential for provider '{provider}'",
            503,
            allocation,
        )

    upstream_model = (
        requested_model if "/" in requested_model else f"{provider}/{requested_model}"
    )
    return PreflightSuccess(
        allocation=allocation,
        provider=provider,
        resolved=resolved,
        upstream_model=upstream_model,
    )
