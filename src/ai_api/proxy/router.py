"""Proxy router: /v1/chat/completions, with call recording."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import Allocation, CallOutcome
from ai_api.observability.logging import redact_string
from ai_api.observability.request_id import current_request_id
from ai_api.proxy import upstream
from ai_api.proxy.auth import parse_bearer_token
from ai_api.proxy.preflight import PreflightRejection, run_preflight
from ai_api.services.pricing import calculate_cost, lookup_price_for_call
from ai_api.services.records import RecordsService

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional chat/completions request fields forwarded verbatim upstream. `model`,
# `messages`, `stream` and `stream_options` are handled explicitly; everything
# here is passed through when the client sends it (None ⇒ omitted so we never
# override litellm/provider defaults).
_CHAT_PASSTHROUGH_FIELDS = (
    "temperature", "top_p", "n", "stop",
    "max_tokens", "max_completion_tokens",
    "presence_penalty", "frequency_penalty", "logit_bias",
    "logprobs", "top_logprobs", "response_format", "seed",
    "tools", "tool_choice", "parallel_tool_calls", "reasoning_effort", "user",
)


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
        "allocation_paused": CallOutcome.rejected_paused,
        "quota_exceeded": CallOutcome.rejected_quota_exceeded,
        "cost_quota_exceeded": CallOutcome.rejected_cost_quota_exceeded,
        "model_forbidden": CallOutcome.rejected_model_forbidden,
        "model_not_responses_capable": CallOutcome.rejected_model_unsupported,
        "response_forbidden": CallOutcome.rejected_response_forbidden,
        "response_not_found": CallOutcome.rejected_response_not_found,
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

    # 3. Shared pre-flight pipeline (auth/allocation/quota/binding/access/credential).
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

    api_key = resolved.api_key
    api_base = resolved.base_url
    api_version = (resolved.extra_config or {}).get("api_version")
    model_key = requested_model.split("/", 1)[-1]
    passthrough = {f: body[f] for f in _CHAT_PASSTHROUGH_FIELDS if body.get(f) is not None}

    # Plain values captured for the streaming generator (must NOT touch the
    # request-scoped session / ORM objects after the handler returns).
    alloc_id = allocation.id
    alloc_subject = allocation.subject_snapshot

    async def _bill(session_: AsyncSession, usage_obj: dict[str, Any]) -> None:
        # Point-in-time pricing: the price effective at started_at.
        price = await lookup_price_for_call(
            session_, provider=provider, model=model_key, call_time=started_at
        )
        cost = calculate_cost(
            price=price,
            prompt_tokens=usage_obj.get("prompt_tokens"),
            completion_tokens=usage_obj.get("completion_tokens"),
        )
        await RecordsService(session_).record_call(
            request_id=request_id,
            allocation_id=alloc_id,
            subject=alloc_subject,
            model=requested_model,
            started_at=started_at,
            status_code=200,
            outcome=CallOutcome.success,
            prompt_tokens=usage_obj.get("prompt_tokens"),
            completion_tokens=usage_obj.get("completion_tokens"),
            total_tokens=usage_obj.get("total_tokens"),
            cost_usd=cost,
        )

    # 4a. Streaming (SSE, billed mid-stream from the final usage chunk)
    if bool(body.get("stream")):
        client_wants_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        # Force include_usage upstream so we always have tokens to bill on, even
        # when the client didn't ask; we strip the usage-only chunk on relay in
        # that case to stay faithful to what they requested.
        stream_options = {**(body.get("stream_options") or {}), "include_usage": True}
        try:
            stream_iter = await upstream.acompletion(
                model=result.upstream_model,
                messages=messages,
                api_key=api_key,
                api_base=api_base,
                api_version=api_version,
                stream=True,
                stream_options=stream_options,
                **passthrough,
            )
        except Exception as e:
            logger.exception("upstream call (stream) failed")
            return await record_and_respond(
                "upstream_error", f"upstream call failed: {e}", status.HTTP_502_BAD_GATEWAY
            )

        async def _record_fresh(usage_obj: dict[str, Any]) -> None:
            # Always a FRESH session: the request-scoped one is closed once the
            # StreamingResponse body runs.
            try:
                async with get_sessionmaker()() as rec_session:
                    await _bill(rec_session, usage_obj)
                    await rec_session.commit()
            except BaseException:  # incl. CancelledError; never lose billing silently
                logger.exception("failed to record streamed chat completion call")

        async def event_gen() -> Any:
            captured_usage: dict[str, Any] = {}
            persisted = False
            try:
                async for chunk in stream_iter:
                    data = (
                        chunk.model_dump_json()
                        if hasattr(chunk, "model_dump_json")
                        else json.dumps(chunk, default=str)
                    )
                    try:
                        payload_obj = json.loads(data)
                    except (ValueError, TypeError):
                        payload_obj = {}
                    usage = payload_obj.get("usage")
                    if usage:
                        captured_usage = usage
                        if not persisted:
                            # Record NOW, while the client is still connected — a
                            # finally-only record loses the row if the client
                            # disconnects right after the usage chunk.
                            await _record_fresh(usage)
                            persisted = True
                        if not client_wants_usage:
                            # Client didn't ask for usage — don't leak it. Some
                            # providers (Azure) attach usage to a choices-present
                            # chunk, others send a choices-empty terminal chunk:
                            # drop the whole chunk if it carries nothing else,
                            # else forward it with usage nulled.
                            if not (payload_obj.get("choices") or []):
                                continue
                            payload_obj["usage"] = None
                            data = json.dumps(payload_obj)
                    yield f"data: {data}\n\n".encode()
                yield b"data: [DONE]\n\n"
            finally:
                # Fallback: stream ended without a usage chunk (provider emitted
                # none / disconnect) — best-effort record so usage isn't lost.
                if not persisted:
                    await _record_fresh(captured_usage)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # 4b. Non-streaming
    try:
        upstream_result = await upstream.acompletion(
            model=result.upstream_model,
            messages=messages,
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            **passthrough,
        )
    except Exception as e:
        logger.exception("upstream call failed")
        return await record_and_respond(
            "upstream_error",
            f"upstream call failed: {e}",
            status.HTTP_502_BAD_GATEWAY,
        )

    payload = upstream_result if isinstance(upstream_result, dict) else upstream_result.model_dump()
    # Non-streaming: handler hasn't returned yet, so the request session is live;
    # get_db_session commits it on teardown.
    await _bill(session, payload.get("usage") or {})
    return payload
