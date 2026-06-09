"""Proxy router: /v1/embeddings — Phase 29 增量①.

Near-clone of /chat/completions (proxy/router.py): same pre-flight pipeline
(auth / allocation / quota / model binding / access policy / credential) and the
same token billing (embeddings are billed as INPUT tokens; no output tokens).
The result IS the embedding response. Lets embedding models in the catalog
actually be called by members (closes 'catalogable ≠ servable' for embeddings).
"""
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
from ai_api.observability.request_id import current_request_id
from ai_api.proxy import upstream
from ai_api.proxy.auth import parse_bearer_token
from ai_api.proxy.preflight import PreflightRejection, run_preflight
from ai_api.proxy.router import _error_payload, _outcome_for_code
from ai_api.services.pricing import calculate_cost, lookup_price_for_call
from ai_api.services.records import RecordsService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/embeddings")
async def proxy_embeddings(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    started_at = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    allocation: Allocation | None = None
    requested_model: str | None = None
    records = RecordsService(session)

    async def record_and_respond(code: str, message: str, http_status: int) -> JSONResponse:
        await records.record_call(
            request_id=request_id,
            allocation_id=allocation.id if allocation else None,
            subject=allocation.subject_snapshot if allocation else None,
            model=requested_model,
            started_at=started_at,
            status_code=http_status,
            outcome=_outcome_for_code(code),
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

    # 2. Body — OpenAI-compatible {model, input}
    try:
        body = await request.json()
    except Exception:
        return await record_and_respond("bad_request", "request body must be JSON", 400)

    requested_model = body.get("model")
    model_input = body.get("input")
    if not isinstance(requested_model, str) or model_input is None:
        return await record_and_respond(
            "bad_request", "request must include 'model' (string) and 'input'", 400
        )

    # 3. Shared pre-flight pipeline (same as /chat/completions).
    settings = get_settings()
    result = await run_preflight(
        session, settings=settings, token=token, requested_model=requested_model
    )
    if isinstance(result, PreflightRejection):
        allocation = result.allocation
        return await record_and_respond(result.code, result.message, result.http_status)
    allocation = result.allocation
    provider = result.provider
    resolved = result.resolved

    # 4. Upstream embedding
    try:
        upstream_result = await upstream.aembedding(
            model=result.upstream_model,
            input=model_input,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            api_version=(resolved.extra_config or {}).get("api_version"),
        )
    except Exception as e:
        logger.exception("upstream embedding call failed")
        return await record_and_respond(
            "upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY
        )

    payload = upstream_result if isinstance(upstream_result, dict) else upstream_result.model_dump()
    usage_obj: dict[str, Any] = payload.get("usage") or {}

    # Billing: embeddings are input-token only. Point-in-time price.
    price = await lookup_price_for_call(
        session, provider=provider, model=requested_model.split("/", 1)[-1], call_time=started_at
    )
    cost = calculate_cost(
        price=price,
        prompt_tokens=usage_obj.get("prompt_tokens"),
        completion_tokens=0,
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
        completion_tokens=0,
        total_tokens=usage_obj.get("total_tokens"),
        cost_usd=cost,
    )
    return payload
