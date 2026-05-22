"""Proxy router: /v1/chat/completions, with call recording."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.config import get_settings
from ai_api.models import Allocation, CallOutcome
from ai_api.observability.logging import redact_string
from ai_api.observability.request_id import current_request_id
from ai_api.proxy import upstream
from ai_api.proxy.allowlist import check_allowed, parse_provider
from ai_api.proxy.auth import parse_bearer_token
from ai_api.proxy.guard import enforce_model_binding
from ai_api.services.allocations import AllocationService
from ai_api.services.pricing import calculate_cost, lookup_price_for_call
from ai_api.services.quota import current_month_usage, is_over_quota
from ai_api.services.records import RecordsService

logger = logging.getLogger(__name__)
router = APIRouter()


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": redact_string(message),
            "request_id": current_request_id() or None,
        }
    }


def _outcome_for_code(code: str) -> CallOutcome:
    return {
        "unauthorized": CallOutcome.rejected_unauthenticated,
        "allocation_revoked": CallOutcome.rejected_revoked,
        "model_mismatch": CallOutcome.rejected_model_mismatch,
        "provider_not_allowed": CallOutcome.rejected_provider,
        "allocation_quarantined": CallOutcome.rejected_quarantined,
        "quota_exceeded": CallOutcome.rejected_quota_exceeded,
        "upstream_error": CallOutcome.upstream_error,
    }.get(code, CallOutcome.gateway_error)


@router.post("/chat/completions")
async def proxy_chat_completions(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    started_at = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    allocation: Allocation | None = None
    requested_model: str | None = None
    records = RecordsService(session)

    async def record_and_respond(
        code: str, message: str, http_status: int
    ) -> JSONResponse:
        outcome = _outcome_for_code(code)
        await records.record_call(
            request_id=request_id,
            allocation_id=allocation.id if allocation else None,
            subject=allocation.subject_snapshot if allocation else None,
            model=requested_model,
            started_at=started_at,
            status_code=http_status,
            outcome=outcome,
            error_message=message,
        )
        return JSONResponse(status_code=http_status, content=_error_payload(code, message))

    # 1. Bearer token
    try:
        token = parse_bearer_token(authorization)
    except HTTPException as exc:
        return await record_and_respond(
            exc.detail["error"]["code"],  # type: ignore[index]
            exc.detail["error"]["message"],  # type: ignore[index]
            exc.status_code,
        )

    # 2. Body
    try:
        body = await request.json()
    except Exception:
        return await record_and_respond("bad_request", "request body must be JSON", 400)

    requested_model = body.get("model")
    messages = body.get("messages")
    if not isinstance(requested_model, str) or not isinstance(messages, list):
        return await record_and_respond(
            "bad_request",
            "request must include 'model' (string) and 'messages' (array)",
            400,
        )

    # Provider allowlist gate (FR-001/002): check before any DB lookups.
    settings = get_settings()
    provider, _ = parse_provider(requested_model)
    if not check_allowed(provider, settings.allowed_providers):
        return await record_and_respond(
            "provider_not_allowed",
            f"provider '{provider}' is not in the allowlist",
            403,
        )

    # 3. Allocation — split lookup from status check so revoked-reject records
    #    can still attribute to the allocation (FR-011 / SC-004).
    alloc_service = AllocationService(session)
    found = await alloc_service.lookup_by_token(token)
    if found is None:
        return await record_and_respond("unauthorized", "invalid credential", 401)
    # Bind to closure now so record_and_respond can attribute the rejection.
    allocation = found
    if allocation.status.value == "revoked":
        return await record_and_respond(
            "allocation_revoked", "allocation has been revoked", 403
        )
    if allocation.status.value == "quarantined":
        return await record_and_respond(
            "allocation_quarantined",
            "allocation is quarantined due to anomalous usage",
            403,
        )

    # Phase 3a: monthly quota check (FR-007)
    if allocation.quota_tokens_per_month is not None:
        usage = await current_month_usage(session, allocation.id)
        if is_over_quota(allocation, usage):
            return await record_and_respond(
                "quota_exceeded",
                f"monthly quota reached ({usage}/{allocation.quota_tokens_per_month} tokens)",
                403,
            )

    # 4. Model binding
    try:
        enforce_model_binding(allocation, requested_model)
    except HTTPException as exc:
        return await record_and_respond(
            exc.detail["error"]["code"],  # type: ignore[index]
            exc.detail["error"]["message"],  # type: ignore[index]
            exc.status_code,
        )

    # 5. Upstream
    try:
        result = await upstream.acompletion(model=requested_model, messages=messages)
    except Exception as e:
        logger.exception("upstream call failed")
        return await record_and_respond(
            "upstream_error",
            f"upstream call failed: {e}",
            status.HTTP_502_BAD_GATEWAY,
        )

    payload = result if isinstance(result, dict) else result.model_dump()
    usage_obj: dict[str, Any] = payload.get("usage") or {}

    # Point-in-time pricing: look up the price effective at started_at.
    price = await lookup_price_for_call(
        session, provider=provider, model=requested_model.split("/", 1)[-1], call_time=started_at
    )
    cost = calculate_cost(
        price=price,
        prompt_tokens=usage_obj.get("prompt_tokens"),
        completion_tokens=usage_obj.get("completion_tokens"),
    )

    await records.record_call(
        request_id=request_id,
        allocation_id=allocation.id,
        subject=allocation.subject_snapshot,
        model=requested_model,
        started_at=started_at,
        status_code=200,
        outcome=CallOutcome.success,
        prompt_tokens=usage_obj.get("prompt_tokens"),
        completion_tokens=usage_obj.get("completion_tokens"),
        total_tokens=usage_obj.get("total_tokens"),
        cost_usd=cost,
    )
    return payload
