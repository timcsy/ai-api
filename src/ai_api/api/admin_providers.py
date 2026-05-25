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
