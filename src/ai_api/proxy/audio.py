"""Proxy router: /v1/audio/speech (TTS) + /v1/audio/transcriptions (STT) — Phase 29 ③ (041).

The two binary-I/O endpoints:
- TTS: text in (JSON) → audio bytes OUT. Billed per CHARACTER (non-token unit).
  Billing is recorded the moment the bytes are in hand (in the handler body, NOT
  a finally) — non-streaming, so the client is still connected (Phase 11 lesson).
- STT: audio file IN (multipart) → text OUT (JSON). Billed as tokens (the response
  carries a token `usage`; per-second metering needs audio duration, which isn't
  available without a new dependency — deferred).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.config import get_settings
from ai_api.models import Allocation, CallOutcome
from ai_api.observability.request_id import current_request_id
from ai_api.proxy import upstream
from ai_api.proxy.auth import parse_bearer_token
from ai_api.proxy.preflight import PreflightRejection, run_preflight
from ai_api.proxy.router import _error_payload, _outcome_for_code
from ai_api.services.pricing import calculate_cost, calculate_unit_cost, lookup_price_for_call
from ai_api.services.records import RecordsService

logger = logging.getLogger(__name__)
router = APIRouter()


def _bearer_or_none(authorization: str | None) -> tuple[str | None, JSONResponse | None]:
    try:
        return parse_bearer_token(authorization), None
    except HTTPException as exc:
        return None, JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                exc.detail["error"]["code"],  # type: ignore[index]
                exc.detail["error"]["message"],  # type: ignore[index]
            ),
        )


# ---------------------------------------------------------------- TTS

@router.post("/audio/speech")
async def proxy_tts(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    started_at = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    allocation: Allocation | None = None
    requested_model: str | None = None
    records = RecordsService(session)

    async def reject(code: str, message: str, http_status: int) -> JSONResponse:
        await records.record_call(
            request_id=request_id, allocation_id=allocation.id if allocation else None,
            subject=allocation.subject_snapshot if allocation else None, model=requested_model,
            started_at=started_at, status_code=http_status, outcome=_outcome_for_code(code),
            error_message=message,
        )
        return JSONResponse(status_code=http_status, content=_error_payload(code, message))

    token, err = _bearer_or_none(authorization)
    if err is not None:
        return err
    assert token is not None

    try:
        body = await request.json()
    except Exception:
        return await reject("bad_request", "request body must be JSON", 400)
    requested_model = body.get("model")
    text = body.get("input")
    voice = body.get("voice") or "alloy"
    if not isinstance(requested_model, str) or not isinstance(text, str):
        return await reject("bad_request", "request must include 'model' and 'input' (string)", 400)

    settings = get_settings()
    result = await run_preflight(
        session, settings=settings, token=token, requested_model=requested_model
    )
    if isinstance(result, PreflightRejection):
        allocation = result.allocation
        return await reject(result.code, result.message, result.http_status)
    allocation = result.allocation
    provider = result.provider
    resolved = result.resolved

    try:
        upstream_result = await upstream.aspeech(
            model=result.upstream_model, input=text, voice=voice,
            api_key=resolved.api_key, api_base=resolved.base_url,
            api_version=(resolved.extra_config or {}).get("api_version"),
        )
    except Exception as e:
        logger.exception("upstream TTS call failed")
        return await reject("upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY)

    audio_bytes = getattr(upstream_result, "content", None)
    if audio_bytes is None:
        audio_bytes = upstream_result if isinstance(upstream_result, bytes) else b""

    # Billing: per character of input text. Record NOW (bytes in hand, non-streaming).
    price = await lookup_price_for_call(
        session, provider=provider, model=requested_model.split("/", 1)[-1], call_time=started_at
    )
    per_char = price.price_per_unit if price is not None and price.price_unit == "character" else None
    cost = calculate_unit_cost(len(text), per_char)
    await records.record_call(
        request_id=request_id, allocation_id=allocation.id, subject=allocation.subject_snapshot,
        model=requested_model, started_at=started_at, status_code=200, outcome=CallOutcome.success,
        quantity=len(text), unit="character", cost_usd=cost,
    )
    return Response(content=audio_bytes, media_type="audio/mpeg")


# ---------------------------------------------------------------- STT

@router.post("/audio/transcriptions")
async def proxy_stt(
    authorization: str | None = Header(default=None, alias="Authorization"),
    model: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    started_at = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    allocation: Allocation | None = None
    records = RecordsService(session)

    async def reject(code: str, message: str, http_status: int) -> JSONResponse:
        await records.record_call(
            request_id=request_id, allocation_id=allocation.id if allocation else None,
            subject=allocation.subject_snapshot if allocation else None, model=model,
            started_at=started_at, status_code=http_status, outcome=_outcome_for_code(code),
            error_message=message,
        )
        return JSONResponse(status_code=http_status, content=_error_payload(code, message))

    token, err = _bearer_or_none(authorization)
    if err is not None:
        return err
    assert token is not None
    if not isinstance(model, str) or file is None:
        return await reject("bad_request", "request must include 'model' (form) and 'file' (upload)", 400)

    settings = get_settings()
    result = await run_preflight(
        session, settings=settings, token=token, requested_model=model
    )
    if isinstance(result, PreflightRejection):
        allocation = result.allocation
        return await reject(result.code, result.message, result.http_status)
    allocation = result.allocation
    provider = result.provider
    resolved = result.resolved

    data = await file.read()
    try:
        upstream_result = await upstream.atranscription(
            model=result.upstream_model, file=(file.filename or "audio", data),
            api_key=resolved.api_key, api_base=resolved.base_url,
            api_version=(resolved.extra_config or {}).get("api_version"),
        )
    except Exception as e:
        logger.exception("upstream STT call failed")
        return await reject("upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY)

    payload = upstream_result if isinstance(upstream_result, dict) else upstream_result.model_dump()
    usage_obj: dict[str, Any] = payload.get("usage") or {}

    # Billing: token-based (per-second needs audio duration, deferred). No usage → cost 0.
    price = await lookup_price_for_call(
        session, provider=provider, model=model.split("/", 1)[-1], call_time=started_at
    )
    cost = calculate_cost(
        price=price,
        prompt_tokens=usage_obj.get("prompt_tokens"),
        completion_tokens=usage_obj.get("completion_tokens") or 0,
    )
    await records.record_call(
        request_id=request_id, allocation_id=allocation.id, subject=allocation.subject_snapshot,
        model=model, started_at=started_at, status_code=200, outcome=CallOutcome.success,
        prompt_tokens=usage_obj.get("prompt_tokens"),
        completion_tokens=usage_obj.get("completion_tokens") or 0,
        total_tokens=usage_obj.get("total_tokens"), cost_usd=cost,
    )
    return payload
