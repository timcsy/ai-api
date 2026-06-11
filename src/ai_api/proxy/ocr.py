"""Proxy router: /v1/ocr — Phase 29 ② (billing generalization).

Near-clone of /v1/embeddings (proxy/embeddings.py): same pre-flight pipeline
(auth / allocation / model binding / access policy / credential) but billed in
PAGES (a non-token unit) via the generalized billing layer. The result IS the
OCR response. Closes 'catalogable ≠ servable' for OCR models and proves the
billing layer can meter non-token units (page / second / character / image …).
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


def _page_count(payload: dict[str, Any]) -> int | None:
    """Pages processed = usage_info.pages_processed if present, else len(pages)."""
    usage = payload.get("usage_info")
    if isinstance(usage, dict) and isinstance(usage.get("pages_processed"), int):
        return int(usage["pages_processed"])
    pages = payload.get("pages")
    return len(pages) if isinstance(pages, list) else None


@router.post("/ocr")
async def proxy_ocr(
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

    # 2. Body — {model, document}
    try:
        body = await request.json()
    except Exception:
        return await record_and_respond("bad_request", "request body must be JSON", 400)

    requested_model = body.get("model")
    document = body.get("document")
    if not isinstance(requested_model, str) or document is None:
        return await record_and_respond(
            "bad_request", "request must include 'model' (string) and 'document'", 400
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

    # 4. Upstream OCR
    try:
        upstream_result = await upstream.aocr(
            model=result.upstream_model,
            document=document,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            api_version=(resolved.extra_config or {}).get("api_version"),
        )
    except Exception as e:
        logger.exception("upstream OCR call failed")
        return await record_and_respond(
            "upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY
        )

    payload = upstream_result if isinstance(upstream_result, dict) else upstream_result.model_dump()

    # Billing: pages x per-page price (point-in-time). Non-token unit.
    pages = _page_count(payload)
    price = await lookup_price_for_call(
        session, provider=provider, model=requested_model.split("/", 1)[-1], call_time=started_at
    )
    per_page = price.price_per_unit if price is not None and price.price_unit == "page" else None
    cost = calculate_unit_cost(pages, per_page)
    await records.record_call(
        request_id=request_id,
        allocation_id=allocation.id,
        subject=allocation.subject_snapshot,
        model=requested_model,
        started_at=started_at,
        status_code=200,
        outcome=CallOutcome.success,
        quantity=pages,
        unit="page",
        cost_usd=cost,
    )
    return payload
