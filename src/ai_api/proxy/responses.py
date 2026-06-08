"""Proxy router: /v1/responses (OpenAI Responses API compatible) — Phase 11.

Shares the pre-flight pipeline with /chat/completions (see proxy/preflight.py).
Routes uniformly through litellm `aresponses` (OpenAI/Azure native high fidelity;
other providers bridged). Supports SSE streaming, tool calls, reasoning, and
server-side conversation state (store / previous_response_id) with per-allocation
attribution isolation.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome
from ai_api.observability.logging import redact_string
from ai_api.observability.request_id import current_request_id
from ai_api.proxy import upstream
from ai_api.proxy.auth import parse_bearer_token
from ai_api.proxy.preflight import PreflightRejection, run_preflight
from ai_api.proxy.router import _error_payload, _outcome_for_code
from ai_api.services import responses_support
from ai_api.services.pricing import calculate_cost, lookup_price_for_call
from ai_api.services.records import RecordsService
from ai_api.services.stored_responses import StoredResponseService

logger = logging.getLogger(__name__)
router = APIRouter()

# Request fields forwarded verbatim to the upstream Responses API.
_PASSTHROUGH_FIELDS = (
    "instructions",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "reasoning",
    "include",
    "store",
    "max_output_tokens",
    "temperature",
    "top_p",
    "text",
    "metadata",
    "truncation",
)

# Diagnostic fields we surface when logging a response.failed event. Skip
# huge user-content fields (instructions/input/output/tools) so the log line
# stays readable.
_FAILED_DIAG_KEYS = (
    "object", "status", "error", "incomplete_details",
    "status_details", "model", "usage", "id", "created_at",
)
# Known non-diagnostic top-level keys; anything outside this set + diag set
# gets surfaced as `extra_keys` so we discover provider-specific extensions.
_FAILED_KNOWN_NOISE_KEYS = frozenset({
    "instructions", "input", "output", "tools", "tool_choice",
    "metadata", "reasoning", "text", "parallel_tool_calls",
    "temperature", "top_p", "max_output_tokens", "previous_response_id",
    "store", "truncation", "stream", "user",
})



def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        dumped: dict[str, Any] = obj.model_dump()
        return dumped
    return {}


def _map_usage(usage: Any) -> dict[str, int | None]:
    """Map Responses usage → CallRecord token fields.

    input_tokens→prompt, output_tokens→completion (incl. reasoning),
    output_tokens_details.reasoning_tokens, input_tokens_details.cached_tokens.
    """
    u = _as_dict(usage)
    otd = _as_dict(u.get("output_tokens_details"))
    itd = _as_dict(u.get("input_tokens_details"))
    return {
        "prompt_tokens": u.get("input_tokens"),
        "completion_tokens": u.get("output_tokens"),
        "total_tokens": u.get("total_tokens"),
        "reasoning_tokens": otd.get("reasoning_tokens"),
        "cached_tokens": itd.get("cached_tokens"),
    }


def _sse(event_type: str | None, data: str) -> bytes:
    prefix = f"event: {event_type}\n" if event_type else ""
    return f"{prefix}data: {data}\n\n".encode()


def _is_auth_failure(exc: BaseException) -> bool:
    """True if an upstream exception looks like a credential auth failure (401/403)."""
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(code, int) and code in (401, 403):
        return True
    text = str(exc).lower()
    return "401" in text or "403" in text or "invalid api key" in text or "unauthorized" in text


async def _maybe_emit_credential_auth_failed(
    exc: BaseException, *, provider: str, credential_id: str | None
) -> None:
    """Phase 13 US3: if an upstream call fails with auth error, emit an audit
    event so admins get notified that a provider credential has gone invalid.

    Uses a fresh session (the request session may be mid-teardown / in error
    state) and never raises — observability must not break the proxy path.
    """
    if not _is_auth_failure(exc):
        return
    try:
        from ai_api.auth import audit
        from ai_api.db import get_sessionmaker
        from ai_api.models import ActorType, AuditEventType

        async with get_sessionmaker()() as s:
            await audit.record(
                s,
                event_type=AuditEventType.provider_credential_auth_failed,
                actor_type=ActorType.system,
                target_type="provider_credential",
                target_id=credential_id,
                details={"provider": provider, "error": str(exc)[:300]},
            )
            await s.commit()
    except BaseException:
        logger.exception("failed to emit provider_credential_auth_failed audit event")


async def _persist_responses_call(
    session: AsyncSession,
    *,
    request_id: str,
    allocation_id: str,
    subject: str | None,
    model: str,
    model_key: str,
    provider: str,
    started_at: datetime,
    usage: Any,
    want_store: bool,
    upstream_response_id: str | None,
) -> None:
    """Bill + record one successful Responses call. Caller commits the session.

    Used both inline (non-streaming, request session) and from the streaming
    generator's finally with a FRESH session — the request-scoped session is
    already closed by the time a StreamingResponse body runs.
    """
    mapped = _map_usage(usage)
    price = await lookup_price_for_call(
        session, provider=provider, model=model_key, call_time=started_at
    )
    cost: Decimal | None = calculate_cost(
        price=price,
        prompt_tokens=mapped["prompt_tokens"],
        completion_tokens=mapped["completion_tokens"],
        cached_tokens=mapped["cached_tokens"],
    )
    await RecordsService(session).record_call(
        request_id=request_id,
        allocation_id=allocation_id,
        subject=subject,
        model=model,
        started_at=started_at,
        status_code=200,
        outcome=CallOutcome.success,
        prompt_tokens=mapped["prompt_tokens"],
        completion_tokens=mapped["completion_tokens"],
        total_tokens=mapped["total_tokens"],
        reasoning_tokens=mapped["reasoning_tokens"],
        cached_tokens=mapped["cached_tokens"],
        cost_usd=cost,
    )
    if want_store and upstream_response_id is not None:
        await StoredResponseService(session).store(
            allocation_id=allocation_id,
            provider=provider,
            upstream_response_id=upstream_response_id,
        )


@router.post("/responses")
async def proxy_responses(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    started_at = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    records = RecordsService(session)
    allocation = None
    requested_model: str | None = None

    async def reject(code: str, message: str, http_status: int) -> JSONResponse:
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
        return await reject(
            exc.detail["error"]["code"],  # type: ignore[index]
            exc.detail["error"]["message"],  # type: ignore[index]
            exc.status_code,
        )

    # 2. Body
    try:
        body = await request.json()
    except Exception:
        return await reject("bad_request", "request body must be JSON", 400)
    requested_model = body.get("model")
    model_input = body.get("input")
    if not isinstance(requested_model, str) or model_input is None:
        return await reject(
            "bad_request", "request must include 'model' (string) and 'input'", 400
        )

    # 3. Shared pre-flight pipeline
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
    # Use the allocation's canonical (prefixed) slug from here on, so a bare Codex
    # slug aliased into scope (gpt-5.4) is treated as its azure/gpt-5.4 model for
    # the capability gate, billing model_key, and stored-response attribution.
    requested_model = result.canonical_model

    # 4. Responses soft gate (Phase 25): don't pre-block on a static flag. The only
    # pre-block is admin's manual "unavailable"; available/unknown are tried, and an
    # unsupported model surfaces the real upstream error below (no info-less 400).
    support = await responses_support.lookup(session, requested_model)
    if support["state"] == "unavailable":
        return await reject(
            "model_responses_disabled",
            f"model '{requested_model}' has been manually disabled for the responses endpoint",
            400,
        )

    # 5. Server-side conversation state: previous_response_id attribution isolation
    stored_svc = StoredResponseService(session)
    passthrough = {k: body.get(k) for k in _PASSTHROUGH_FIELDS if body.get(k) is not None}
    prev_id = body.get("previous_response_id")
    if prev_id is not None:
        owned = await stored_svc.resolve_for_continuation(
            response_id=prev_id, allocation_id=allocation.id, provider=provider
        )
        if owned == "not_found":
            return await reject("response_not_found", "previous response not found or expired", 404)
        if owned == "forbidden":
            return await reject(
                "response_forbidden", "previous response does not belong to this allocation", 403
            )
        passthrough["previous_response_id"] = owned

    want_store = bool(body.get("store"))
    stream = bool(body.get("stream"))

    api_key = resolved.api_key
    api_base = resolved.base_url
    api_version = (resolved.extra_config or {}).get("api_version")

    model_key = requested_model.split("/", 1)[-1]
    # Plain values captured for the streaming generator (must not touch the
    # request-scoped `session`/ORM objects after the handler returns).
    alloc_id = allocation.id
    alloc_subject = allocation.subject_snapshot

    # 6a. Streaming
    if stream:
        try:
            stream_iter = await upstream.aresponses(
                model=result.upstream_model,
                input=model_input,
                api_key=api_key,
                api_base=api_base,
                api_version=api_version,
                stream=True,
                **passthrough,
            )
        except Exception as e:
            logger.exception("upstream responses (stream) failed")
            await _maybe_emit_credential_auth_failed(
                e, provider=provider, credential_id=getattr(resolved, "id", None)
            )
            return await reject("upstream_error", f"upstream call failed: {e}", 502)

        async def _record_fresh(usage: Any, resp_id: str | None) -> None:
            # Always a FRESH session: the request-scoped one is already closed
            # once the StreamingResponse body runs.
            try:
                async with get_sessionmaker()() as rec_session:
                    await _persist_responses_call(
                        rec_session,
                        request_id=request_id,
                        allocation_id=alloc_id,
                        subject=alloc_subject,
                        model=requested_model,
                        model_key=model_key,
                        provider=provider,
                        started_at=started_at,
                        usage=usage,
                        want_store=want_store,
                        upstream_response_id=resp_id,
                    )
                    await rec_session.commit()
            except BaseException:  # incl. CancelledError; never lose billing silently
                logger.exception("failed to record streamed responses call")

        async def _record_failed_stream(error_message: str) -> None:
            # Upstream emitted response.failed mid-stream — record an
            # upstream_error row (no usage/cost) so admin sees the call in
            # usage views and the log line points at WHY upstream failed.
            try:
                async with get_sessionmaker()() as rec_session:
                    await RecordsService(rec_session).record_call(
                        request_id=request_id,
                        allocation_id=alloc_id,
                        subject=alloc_subject,
                        model=requested_model,
                        started_at=started_at,
                        status_code=200,  # transport was 200; the failure is in-stream
                        outcome=CallOutcome.upstream_error,
                        error_message=error_message[:500],
                    )
                    await rec_session.commit()
            except BaseException:
                logger.exception("failed to record upstream_error responses call")

        async def event_gen() -> Any:
            captured_usage: Any = None
            captured_resp_id: str | None = None
            persisted = False
            try:
                async for event in stream_iter:
                    data = (
                        event.model_dump_json()
                        if hasattr(event, "model_dump_json")
                        else json.dumps(event, default=str)
                    )
                    # Derive the SSE event type from the serialized payload's
                    # `type` (the OpenAI wire value, e.g. "response.completed").
                    # litellm's event.type is an enum whose repr would otherwise
                    # leak (e.g. "ResponsesAPIStreamEvents.RESPONSE_COMPLETED")
                    # and break Codex + usage capture.
                    try:
                        payload_obj = json.loads(data)
                    except (ValueError, TypeError):
                        payload_obj = {}
                    etype = payload_obj.get("type")
                    if etype == "response.completed" and not persisted:
                        resp = _as_dict(payload_obj.get("response"))
                        captured_usage = resp.get("usage")
                        captured_resp_id = resp.get("id")
                        # Record NOW, while the client is still connected — doing
                        # it in `finally` loses the row when the client (e.g. Codex)
                        # disconnects right after `response.completed` and cancels
                        # the task mid-await.
                        await _record_fresh(captured_usage, captured_resp_id)
                        persisted = True
                    elif etype == "response.failed" and not persisted:
                        # Upstream protocol-level failure (content filter, model
                        # not found on deployment, capacity, etc.). Try several
                        # known locations — Azure/OpenAI/litellm don't always put
                        # the reason in `response.error`; sometimes it's in
                        # `incomplete_details.reason` or `status_details.error`.
                        resp = _as_dict(payload_obj.get("response"))
                        err = _as_dict(resp.get("error"))
                        incomplete = _as_dict(resp.get("incomplete_details"))
                        status_details = _as_dict(resp.get("status_details"))
                        sd_err = _as_dict(status_details.get("error"))
                        err_code = (
                            err.get("code")
                            or sd_err.get("code")
                            or incomplete.get("reason")
                            or resp.get("status")
                            or "unknown"
                        )
                        err_msg = (
                            err.get("message")
                            or sd_err.get("message")
                            or incomplete.get("description")
                            or "(no error message)"
                        )
                        # Dump only diagnostic fields (see module-level
                        # _FAILED_DIAG_KEYS) and list any unexpected top-level
                        # keys for discovering provider-specific extensions.
                        diag = {k: resp.get(k) for k in _FAILED_DIAG_KEYS if k in resp}
                        extra_keys = sorted(
                            set(resp.keys())
                            - set(_FAILED_DIAG_KEYS)
                            - _FAILED_KNOWN_NOISE_KEYS
                        )
                        logger.error(
                            "responses stream upstream failure model=%s provider=%s "
                            "allocation=%s code=%s message=%s diag=%s extra_keys=%s",
                            requested_model, provider, alloc_id, err_code, err_msg,
                            json.dumps(diag, default=str)[:2000], extra_keys,
                        )
                        await _record_failed_stream(f"{err_code}: {err_msg}")
                        persisted = True
                    yield _sse(etype, data)
            except Exception as ex:
                # litellm may raise mid-stream after a synthetic response.failed
                # event — capture the exception so the underlying upstream reason
                # surfaces in logs.
                logger.exception(
                    "responses stream raised model=%s provider=%s allocation=%s",
                    requested_model, provider, alloc_id,
                )
                if not persisted:
                    await _record_failed_stream(f"stream_exception: {ex}"[:500])
                    persisted = True
            finally:
                # Fallback: stream ended without a completed/failed event
                # (cut/disconnect) — record best-effort so usage isn't silently dropped.
                if not persisted:
                    await _record_fresh(captured_usage, captured_resp_id)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # 6b. Non-streaming
    try:
        upstream_result = await upstream.aresponses(
            model=result.upstream_model,
            input=model_input,
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            **passthrough,
        )
    except Exception as e:
        logger.exception("upstream responses failed")
        await _maybe_emit_credential_auth_failed(
            e, provider=provider, credential_id=getattr(resolved, "id", None)
        )
        return await reject("upstream_error", f"upstream call failed: {e}", 502)

    payload = _as_dict(upstream_result) if not isinstance(upstream_result, dict) else upstream_result
    # Non-streaming: handler hasn't returned yet, so the request session is live;
    # get_db_session commits it on teardown.
    await _persist_responses_call(
        session,
        request_id=request_id,
        allocation_id=alloc_id,
        subject=alloc_subject,
        model=requested_model,
        model_key=model_key,
        provider=provider,
        started_at=started_at,
        usage=payload.get("usage"),
        want_store=want_store,
        upstream_response_id=payload.get("id"),
    )
    return payload


# Re-export so callers/tests can patch a single redact entrypoint consistently.
__all__ = ["redact_string", "router"]
