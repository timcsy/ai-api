"""Phase 31 (042): the shared execution engine for data-driven endpoints.

run_endpoint(spec, ...) is the unchanging flow that every non-streaming member
inference endpoint shares — written once, parameterised by an EndpointSpec:

    bearer → parse (per io shape) → validate required → run_preflight
    → spec.call (upstream) → meter → record_call → respond (per io shape)

The 5 copy-pasted handlers (embeddings/ocr/images/rerank/audio) collapse into
this engine + one EndpointSpec each (registry.py).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.config import get_settings
from ai_api.models import Allocation, CallOutcome
from ai_api.observability.request_id import current_request_id
from ai_api.proxy.auth import parse_bearer_token
from ai_api.proxy.endpoint_spec import EndpointSpec, InputShape, OutputShape
from ai_api.proxy.preflight import PreflightRejection, run_preflight
from ai_api.proxy.router import _error_payload, _outcome_for_code
from ai_api.services.pricing import lookup_price_for_call
from ai_api.services.records import RecordsService

logger = logging.getLogger(__name__)


async def _parse(spec: EndpointSpec, request: Request) -> tuple[str | None, dict[str, Any]] | None:
    """Return (model, fields) or None if the request couldn't be parsed."""
    if spec.input_shape == InputShape.json:
        try:
            body = await request.json()
        except Exception:
            return None
        if not isinstance(body, dict):
            return None
        return body.get(spec.model_field), dict(body)
    # multipart: form fields; UploadFile → (filename, bytes)
    form = await request.form()
    fields: dict[str, Any] = {}
    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            fields[key] = (value.filename or "upload", await value.read())
        else:
            fields[key] = value
    model = fields.get(spec.model_field)
    return (model if isinstance(model, str) else None), fields


async def run_endpoint(
    spec: EndpointSpec,
    request: Request,
    authorization: str | None,
    session: AsyncSession,
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

    # 2. Parse (per input shape) + validate required fields
    parsed = await _parse(spec, request)
    if parsed is None:
        return await record_and_respond("bad_request", "request body could not be parsed", 400)
    requested_model, fields = parsed
    if not isinstance(requested_model, str) or any(
        fields.get(k) is None for k in spec.required
    ):
        need = ", ".join(["'model'", *(f"'{k}'" for k in spec.required)])
        return await record_and_respond("bad_request", f"request must include {need}", 400)

    # 3. Shared pre-flight pipeline
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

    # 4. Upstream call (per spec)
    try:
        upstream_result = await spec.call(fields, resolved, result.upstream_model)
    except Exception as e:
        logger.exception("upstream call failed (%s)", spec.path)
        return await record_and_respond(
            "upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY
        )

    # 5. Shape the payload / extract bytes (per output shape)
    if spec.output_shape == OutputShape.binary:
        body_bytes = getattr(upstream_result, "content", None)
        if body_bytes is None:
            body_bytes = upstream_result if isinstance(upstream_result, bytes) else b""
        payload: dict[str, Any] = {}
    else:
        payload = upstream_result if isinstance(upstream_result, dict) else upstream_result.model_dump()
        body_bytes = b""

    # 6. Meter + bill (point-in-time price)
    price = await lookup_price_for_call(
        session, provider=provider, model=requested_model.split("/", 1)[-1], call_time=started_at
    )
    metering = spec.meter.measure(fields, payload, price)

    # 7. Record the successful call (in-handler, non-streaming → client still connected)
    await records.record_call(
        request_id=request_id,
        allocation_id=allocation.id,
        subject=allocation.subject_snapshot,
        model=requested_model,
        started_at=started_at,
        status_code=200,
        outcome=CallOutcome.success,
        cost_usd=metering.cost,
        **metering.record_kwargs,
    )

    # 8. Respond (per output shape)
    if spec.output_shape == OutputShape.binary:
        return Response(content=body_bytes, media_type=spec.binary_media_type)
    return payload
