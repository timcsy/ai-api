"""Phase 5 US2: admin provider credential CRUD + rotate + disable.

Contract: specs/012-multi-provider-access/contracts/providers.yaml
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.config import get_settings
from ai_api.models import ProviderCredential, ProviderCredentialStatus
from ai_api.services.provider_credentials import (
    AlreadyDisabledError,
    CannotRotateError,
    DuplicateLabelError,
    ProviderCredentialService,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


class CreateProviderRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=8)
    base_url: str | None = None
    extra_config: dict[str, Any] | None = None


class RotateProviderRequest(BaseModel):
    api_key: str = Field(min_length=8)


def _public(c: ProviderCredential) -> dict[str, Any]:
    return {
        "id": c.id,
        "provider": c.provider,
        "label": c.label,
        "fingerprint": c.fingerprint,
        "base_url": c.base_url,
        "extra_config": c.extra_config,
        "status": c.status.value,
        "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
        "created_at": c.created_at.isoformat(),
        "created_by": c.created_by,
        "disabled_at": c.disabled_at.isoformat() if c.disabled_at else None,
    }


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


@router.get("/providers")
async def list_providers(
    provider: str | None = Query(default=None),
    status_q: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    status_enum: ProviderCredentialStatus | None = None
    if status_q is not None:
        try:
            status_enum = ProviderCredentialStatus(status_q)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=_err("bad_status", f"invalid status: {status_q}"),
            ) from exc
    rows = await ProviderCredentialService(session).list(provider=provider, status=status_enum)
    return [_public(r) for r in rows]


@router.get("/providers/{credential_id}")
async def get_provider(
    credential_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    cred = await ProviderCredentialService(session).get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "credential not found"))
    return _public(cred)


@router.post(
    "/providers",
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    payload: CreateProviderRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from sqlalchemy import select as _select
    from ai_api.services.provider_credentials import _fingerprint

    settings = get_settings()
    if payload.provider not in settings.allowed_providers:
        raise HTTPException(
            status_code=422,
            detail=_err(
                "provider_not_allowed",
                f"provider '{payload.provider}' is not in ALLOWED_PROVIDERS",
            ),
        )
    service = ProviderCredentialService(session)
    # Pre-check: same fingerprint already exists for this provider → warn (still
    # allowed because admin might intentionally duplicate, but signal it back).
    target_fp = _fingerprint(payload.api_key)
    dup = (await session.execute(
        _select(ProviderCredential).where(
            ProviderCredential.provider == payload.provider,
            ProviderCredential.fingerprint == target_fp,
        )
    )).scalar_one_or_none()
    try:
        cred = await service.create(
            provider=payload.provider,
            label=payload.label,
            api_key=payload.api_key,
            base_url=payload.base_url,
            extra_config=payload.extra_config,
        )
    except DuplicateLabelError as exc:
        raise HTTPException(status_code=409, detail=_err("duplicate_label", str(exc))) from exc
    body = _public(cred)
    body["api_key"] = payload.api_key  # one-time plaintext echo
    if dup is not None:
        body["warning"] = {
            "code": "duplicate_fingerprint",
            "message": f"another credential ({dup.label}) already uses this key",
            "existing_id": dup.id,
            "existing_label": dup.label,
        }
    return body


@router.post("/providers/{credential_id}/rotate")
async def rotate_provider(
    credential_id: str,
    payload: RotateProviderRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProviderCredentialService(session)
    try:
        cred = await service.rotate(credential_id, payload.api_key)
    except CannotRotateError as exc:
        raise HTTPException(status_code=409, detail=_err("cannot_rotate", str(exc))) from exc
    if cred is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "credential not found"))
    body = _public(cred)
    body["api_key"] = payload.api_key
    return body


@router.post("/providers/{credential_id}/disable")
async def disable_provider(
    credential_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProviderCredentialService(session)
    try:
        cred = await service.disable(credential_id)
    except AlreadyDisabledError as exc:
        raise HTTPException(
            status_code=409, detail=_err("already_disabled", str(exc))
        ) from exc
    if cred is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "credential not found"))
    return _public(cred)


# Default 1-token-ping model per provider for test-connection.
_DEFAULT_TEST_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "gemini": "gemini-1.5-flash",
}


@router.post("/providers/{credential_id}/test-connection")
async def test_provider_connection(
    credential_id: str,
    model: str | None = Query(default=None, description="Override default per-provider test model"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Issue a minimal chat completion via this credential to verify it works.

    Returns `{ok: true, model, latency_ms}` on success, or
    `{ok: false, error_type, message}` on failure. NEVER raises 5xx for
    upstream errors — the test result IS the response.
    """
    import time

    from ai_api.proxy import upstream
    from ai_api.services.crypto import decrypt_str

    cred = await ProviderCredentialService(session).get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "credential not found"))
    if cred.status != ProviderCredentialStatus.active:
        raise HTTPException(
            status_code=409,
            detail=_err("not_active", f"credential is {cred.status.value}"),
        )

    settings = get_settings()
    if model is None:
        if cred.provider == "azure":
            model = settings.azure_openai_test_model or "gpt-4o-mini"
        else:
            model = _DEFAULT_TEST_MODELS.get(cred.provider, "")
        if not model:
            raise HTTPException(
                status_code=422,
                detail=_err(
                    "no_default_model",
                    f"no default test model for provider {cred.provider!r}; pass ?model=...",
                ),
            )

    from datetime import UTC, datetime as _dt

    upstream_model = f"{cred.provider}/{model}" if "/" not in model else model
    api_key = decrypt_str(cred.enc_key)
    extra = cred.extra_config or {}
    started = time.perf_counter()
    try:
        await upstream.acompletion(
            model=upstream_model,
            messages=[{"role": "user", "content": "ping"}],
            api_key=api_key,
            api_base=cred.base_url,
            api_version=extra.get("api_version"),
            max_tokens=16,
        )
    except Exception as exc:
        # Test that successfully connected (any non-network error counts as
        # "we reached the upstream") still updates last_used_at so admins can
        # see when they last verified each credential.
        cred.last_used_at = _dt.now(UTC)
        await session.flush()
        return {
            "ok": False,
            "model": upstream_model,
            "error_type": type(exc).__name__,
            "message": str(exc)[:512],
        }
    latency_ms = int((time.perf_counter() - started) * 1000)
    cred.last_used_at = _dt.now(UTC)
    await session.flush()
    return {
        "ok": True,
        "model": upstream_model,
        "latency_ms": latency_ms,
    }
