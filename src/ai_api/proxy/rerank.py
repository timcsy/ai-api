"""Proxy router: /v1/rerank — Phase 29 ③ (041).

Near-clone of /v1/ocr: same pre-flight pipeline, billed per QUERY (a non-token
unit) via the generalized billing layer. JSON in (query + documents) / out
(ranked results).
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
from ai_api.services.pricing import calculate_unit_cost, lookup_price_for_call
from ai_api.services.records import RecordsService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/rerank")
async def proxy_rerank(
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

    # 2. Body — {model, query, documents}
    try:
        body = await request.json()
    except Exception:
        return await record_and_respond("bad_request", "request body must be JSON", 400)

    requested_model = body.get("model")
    query = body.get("query")
    documents = body.get("documents")
    if not isinstance(requested_model, str) or not isinstance(query, str) or not isinstance(documents, list):
        return await record_and_respond(
            "bad_request", "request must include 'model', 'query' (string) and 'documents' (list)", 400
        )

    # 3. Shared pre-flight pipeline.
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

    # 4. Upstream rerank
    try:
        upstream_result = await upstream.arerank(
            model=result.upstream_model,
            query=query,
            documents=documents,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            api_version=(resolved.extra_config or {}).get("api_version"),
        )
    except Exception as e:
        logger.exception("upstream rerank call failed")
        return await record_and_respond(
            "upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY
        )

    payload = upstream_result if isinstance(upstream_result, dict) else upstream_result.model_dump()

    # Billing: one query (non-token unit).
    price = await lookup_price_for_call(
        session, provider=provider, model=requested_model.split("/", 1)[-1], call_time=started_at
    )
    per_query = price.price_per_unit if price is not None and price.price_unit == "query" else None
    cost = calculate_unit_cost(1, per_query)
    await records.record_call(
        request_id=request_id,
        allocation_id=allocation.id,
        subject=allocation.subject_snapshot,
        model=requested_model,
        started_at=started_at,
        status_code=200,
        outcome=CallOutcome.success,
        quantity=1,
        unit="query",
        cost_usd=cost,
    )
    return payload
