"""Phase 32 (043): /v1/realtime — OpenAI-compatible live transcription relay.

A thin bidirectional WebSocket relay between an app client and the upstream
provider's realtime WS. We do NOT go through litellm's realtime (it is Proxy form
/ client-direct, which bypasses the gateway and loses per-allocation attribution +
in-flight revocation — see experience lesson 40). Instead we borrow litellm
`RealTimeStreaming.bidirectional_forward` *structure*: two forwarding coroutines,
plus a side-channel revocation watcher, plus per-minute metering self-counted from
the client's `input_audio_buffer.append` PCM bytes (research R2 — no reliance on a
provider usage event, so an abnormal abort never loses billing).

Testability: `handle_realtime` takes an injectable `open_upstream`, so CI exercises
the full relay/metering/revocation against a fake provider WS in-loop (the engine is
bound to the test event loop; a separate TestClient portal would break asyncpg).
Real Azure realtime WS is validated by the maintainer in quickstart (T027).
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter()

# --- WebSocket close codes (RFC 6455) used when the platform closes ---------
WS_NORMAL = 1000
WS_POLICY_VIOLATION = 1008  # auth / quota / revoked
WS_UNSUPPORTED = 1003       # model is not a realtime kind
WS_INTERNAL = 1011          # upstream error / unexpected

# Default revocation re-check interval (seconds). Long-lived connections MUST be
# re-checked, not only at connect (principle 3). Centralized + overridable.
REVOKE_RECHECK_SECONDS = 5

# PCM defaults when `session.update` omits them: 16-bit mono.
_DEFAULT_BYTES_PER_SAMPLE = 2
_DEFAULT_CHANNELS = 1
_DEFAULT_SAMPLE_RATE = 24000


# --- Uniform WS interfaces (FastAPI WebSocket and the websockets client both
# satisfy these; test fakes mirror them) ------------------------------------
class ClientWS(Protocol):
    @property
    def headers(self) -> Any: ...

    async def accept(self) -> None: ...
    async def receive_text(self) -> str: ...
    async def send_text(self, data: str) -> None: ...
    async def close(self, code: int = WS_NORMAL, reason: str | None = None) -> None: ...


class UpstreamWS(Protocol):
    async def send(self, data: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


# open_upstream(provider, model, api_key, api_base, api_version) -> UpstreamWS
OpenUpstream = Callable[..., Awaitable[UpstreamWS]]


@dataclass
class RealtimeSession:
    """In-memory lifecycle state of one realtime connection (never persisted).

    On disconnect (any reason) the accrued `audio_bytes` is metered into a single
    CallRecord(unit="minute") attributed to `allocation_id`.
    """

    allocation_id: str
    subject: str | None
    resource_model: str
    upstream_model: str
    provider: str
    request_id: str
    started_at: datetime
    audio_bytes: int = 0
    sample_rate: int = _DEFAULT_SAMPLE_RATE
    bytes_per_sample: int = _DEFAULT_BYTES_PER_SAMPLE
    channels: int = _DEFAULT_CHANNELS
    # normal | client_abort | upstream_error | revoked
    close_reason: str = "normal"


# --- Pure metering helpers (T014/T017) --------------------------------------
def duration_seconds(audio_bytes: int, sample_rate: int, bytes_per_sample: int, channels: int) -> float:
    """Audio duration from raw PCM byte count. 0 if the frame geometry is unknown."""
    denom = sample_rate * bytes_per_sample * channels
    if denom <= 0:
        return 0.0
    return audio_bytes / denom


def pcm_bytes_to_minutes(
    audio_bytes: int,
    *,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
    bytes_per_sample: int = _DEFAULT_BYTES_PER_SAMPLE,
    channels: int = _DEFAULT_CHANNELS,
) -> int:
    """Per-minute billing quantity: round UP to the next whole minute (a started
    minute is a billed minute, the per-minute convention). 0 bytes → 0 minutes."""
    secs = duration_seconds(audio_bytes, sample_rate, bytes_per_sample, channels)
    if secs <= 0:
        return 0
    return math.ceil(secs / 60)


def pcm_bytes_to_seconds(
    audio_bytes: int,
    *,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
    bytes_per_sample: int = _DEFAULT_BYTES_PER_SAMPLE,
    channels: int = _DEFAULT_CHANNELS,
) -> int:
    """Per-second billing quantity: round UP to the next whole second (litellm
    prices gpt-realtime-whisper via ``input_cost_per_second``). 0 bytes → 0."""
    secs = duration_seconds(audio_bytes, sample_rate, bytes_per_sample, channels)
    if secs <= 0:
        return 0
    return math.ceil(secs)


def session_minutes(sess: RealtimeSession) -> int:
    return pcm_bytes_to_minutes(
        sess.audio_bytes,
        sample_rate=sess.sample_rate,
        bytes_per_sample=sess.bytes_per_sample,
        channels=sess.channels,
    )


def session_quantity(sess: RealtimeSession, unit: str) -> int:
    """Billable quantity in the unit the PriceList carries. litellm prices realtime
    transcription per SECOND; admins may instead price per minute — bill in whichever
    the price row uses so cost = quantity x per-unit lines up."""
    if unit == "minute":
        return session_minutes(sess)
    return pcm_bytes_to_seconds(
        sess.audio_bytes,
        sample_rate=sess.sample_rate,
        bytes_per_sample=sess.bytes_per_sample,
        channels=sess.channels,
    )


def _apply_format(sess: RealtimeSession, ev: dict[str, Any]) -> None:
    """Read sample rate (and, if present, sample width/channels) from a
    `session.update` so metering uses the client's actual PCM geometry. Tolerant of
    the two shapes seen in the wild: session.audio.input.format.* and
    session.input_audio_format / session.audio.format.*."""
    session = ev.get("session")
    if not isinstance(session, dict):
        return
    fmt: dict[str, Any] = {}
    audio = session.get("audio")
    if isinstance(audio, dict):
        inp = audio.get("input")
        if isinstance(inp, dict) and isinstance(inp.get("format"), dict):
            fmt = inp["format"]
        elif isinstance(audio.get("format"), dict):
            fmt = audio["format"]
    if not fmt and isinstance(session.get("input_audio_format"), dict):
        fmt = session["input_audio_format"]
    rate = fmt.get("rate") or fmt.get("sample_rate")
    if isinstance(rate, int) and rate > 0:
        sess.sample_rate = rate
    channels = fmt.get("channels")
    if isinstance(channels, int) and channels > 0:
        sess.channels = channels
    bps = fmt.get("bytes_per_sample")
    if isinstance(bps, int) and bps > 0:
        sess.bytes_per_sample = bps


def _meter_client_event(sess: RealtimeSession, raw: str) -> None:
    """Update metering state from a client→platform frame. Never raises."""
    try:
        ev = json.loads(raw)
    except (ValueError, TypeError):
        return
    if not isinstance(ev, dict):
        return
    etype = ev.get("type")
    if etype == "session.update":
        _apply_format(sess, ev)
    elif etype == "input_audio_buffer.append":
        audio = ev.get("audio")
        if isinstance(audio, str) and audio:
            # Malformed base64 → skip metering this frame (never crash the relay).
            with contextlib.suppress(ValueError, TypeError):
                sess.audio_bytes += len(base64.b64decode(audio, validate=False))


# --- Bidirectional relay (T011) ---------------------------------------------
async def _client_to_upstream(client: ClientWS, upstream: UpstreamWS, sess: RealtimeSession) -> None:
    while True:
        try:
            raw = await client.receive_text()
        except Exception:
            # Client closed / aborted. Accrued audio_bytes is already counted, so
            # billing on disconnect never loses usage (FR-004/SC-003).
            if sess.close_reason == "normal":
                sess.close_reason = "client_abort"
            return
        _meter_client_event(sess, raw)
        try:
            await upstream.send(raw)
        except Exception:
            if sess.close_reason == "normal":
                sess.close_reason = "upstream_error"
            return


async def _upstream_to_client(client: ClientWS, upstream: UpstreamWS, sess: RealtimeSession) -> None:
    while True:
        try:
            raw = await upstream.recv()
        except Exception:
            if sess.close_reason == "normal":
                sess.close_reason = "upstream_error"
            return
        try:
            await client.send_text(raw)
        except Exception:
            if sess.close_reason == "normal":
                sess.close_reason = "client_abort"
            return


# check_active(allocation_id) -> bool
CheckActive = Callable[[str], Awaitable[bool]]


async def _revocation_watch(
    sess: RealtimeSession,
    *,
    stop: asyncio.Event,
    check_active: CheckActive,
    interval: float,
) -> None:
    """Side-channel: every `interval` seconds re-check the allocation; if it is no
    longer active (revoked / paused / quarantined) flip close_reason and signal the
    relay to stop (FR-005). Does not touch the relay hot path."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return  # relay ended first
        except TimeoutError:
            pass
        try:
            active = await check_active(sess.allocation_id)
        except Exception:
            logger.exception("realtime revocation re-check failed; leaving connection up")
            continue
        if not active:
            sess.close_reason = "revoked"
            stop.set()
            return


async def run_relay(
    client: ClientWS,
    upstream: UpstreamWS,
    sess: RealtimeSession,
    *,
    check_active: CheckActive,
    interval: float = REVOKE_RECHECK_SECONDS,
) -> None:
    """Run both forwarding coroutines + the revocation watcher until any one ends,
    then tear the others down. Returns once the connection is fully closed."""
    stop = asyncio.Event()

    async def _forward_then_stop(coro: Awaitable[None]) -> None:
        try:
            await coro
        finally:
            stop.set()

    t_up = asyncio.create_task(_forward_then_stop(_client_to_upstream(client, upstream, sess)))
    t_down = asyncio.create_task(_forward_then_stop(_upstream_to_client(client, upstream, sess)))
    t_watch = asyncio.create_task(
        _revocation_watch(sess, stop=stop, check_active=check_active, interval=interval)
    )

    await stop.wait()
    # Closing both ends unblocks any coroutine parked in recv/receive.
    await _safe_close_upstream(upstream)
    await _safe_close_client(
        client,
        *_close_code_for(sess.close_reason),
    )
    for task in (t_up, t_down, t_watch):
        task.cancel()
    await asyncio.gather(t_up, t_down, t_watch, return_exceptions=True)


def _close_code_for(close_reason: str) -> tuple[int, str]:
    if close_reason == "revoked":
        return WS_POLICY_VIOLATION, "allocation revoked"
    if close_reason == "upstream_error":
        return WS_INTERNAL, "upstream connection closed"
    return WS_NORMAL, "connection closed"


async def _safe_close_client(client: ClientWS, code: int, reason: str) -> None:
    # Best-effort: the peer may already be gone / mid-teardown.
    with contextlib.suppress(Exception):
        await client.close(code=code, reason=reason)


async def _safe_close_upstream(upstream: UpstreamWS) -> None:
    with contextlib.suppress(Exception):
        await upstream.close()


# --- Outcome mapping + billing (T018) ---------------------------------------
def _outcome_for_close(close_reason: str) -> Any:
    from ai_api.models import CallOutcome

    if close_reason == "upstream_error":
        return CallOutcome.upstream_error
    # normal / client_abort / revoked all delivered service for the accrued
    # minutes → success (usage is real). revoked just terminated it early.
    return CallOutcome.success


async def _bill_session(sess: RealtimeSession) -> None:
    """Write ONE CallRecord for the accrued audio, in the unit the PriceList carries
    (litellm prices realtime transcription per SECOND; admins may price per minute).
    Any close path reaches here (FR-004). Uses a fresh session — the connection has no
    request session. Never raises (billing must not crash teardown)."""
    from ai_api.db import get_sessionmaker
    from ai_api.services.pricing import calculate_unit_cost, lookup_price_for_call
    from ai_api.services.records import RecordsService

    outcome = _outcome_for_close(sess.close_reason)
    try:
        async with get_sessionmaker()() as s:
            price = await lookup_price_for_call(
                s,
                provider=sess.provider,
                model=sess.upstream_model.split("/", 1)[-1],
                call_time=sess.started_at,
            )
            # Bill in the price's unit (second from litellm, or minute); default to
            # second (litellm's native unit) when unpriced so the quantity is honest.
            unit = price.price_unit if (price and price.price_unit in ("second", "minute")) else "second"
            quantity = session_quantity(sess, unit)
            cost = (
                calculate_unit_cost(quantity, price.price_per_unit)
                if price is not None
                else None
            )
            await RecordsService(s).record_call(
                request_id=sess.request_id,
                allocation_id=sess.allocation_id,
                subject=sess.subject,
                model=sess.resource_model,
                started_at=sess.started_at,
                status_code=200,
                outcome=outcome,
                quantity=quantity,
                unit=unit,
                cost_usd=cost,
                error_message=(
                    "allocation revoked mid-connection" if sess.close_reason == "revoked" else None
                ),
            )
            await s.commit()
    except BaseException:  # incl. CancelledError; never lose billing silently
        logger.exception("failed to record realtime call (allocation=%s)", sess.allocation_id)


# --- Allocation status re-check (used as check_active) ----------------------
async def _allocation_is_active(allocation_id: str) -> bool:
    from ai_api.db import get_sessionmaker
    from ai_api.models import Allocation, AllocationStatus

    try:
        async with get_sessionmaker()() as s:
            alloc = await s.get(Allocation, allocation_id)
            return alloc is not None and alloc.status == AllocationStatus.active
    except Exception:
        logger.exception("realtime allocation re-check query failed")
        # Fail-open on a transient DB error: do NOT kill a live connection on a
        # blip; the next tick re-checks.
        return True


# --- Connection entrypoint (T010/T012/T013) ---------------------------------
def _extract_token(headers: Any) -> str | None:
    """Bearer token from the Authorization header (case-insensitive lookup)."""
    auth = None
    if hasattr(headers, "get"):
        auth = headers.get("authorization") or headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    return token or None


async def handle_realtime(
    client: ClientWS,
    *,
    open_upstream: OpenUpstream,
    check_active: CheckActive = _allocation_is_active,
    revoke_interval: float = REVOKE_RECHECK_SECONDS,
) -> None:
    """Drive one realtime connection end-to-end. Injectable `open_upstream` /
    `check_active` make the whole path CI-testable against a fake provider WS."""
    from ai_api.config import get_settings
    from ai_api.db import get_sessionmaker
    from ai_api.models import ModelCatalog
    from ai_api.observability.request_id import current_request_id
    from ai_api.proxy.preflight import PreflightRejection, run_preflight
    from ai_api.services.model_kind import model_kind

    await client.accept()
    started_at = datetime.now(UTC)
    request_id = current_request_id() or "realtime"

    token = _extract_token(client.headers)
    if token is None:
        logger.info("realtime connection rejected: missing bearer token")
        await _safe_close_client(client, WS_POLICY_VIOLATION, "missing bearer token")
        return

    # First frame carries the model (session.update). Need it for preflight.
    try:
        first_raw = await client.receive_text()
    except Exception:
        await _safe_close_client(client, WS_NORMAL, "no session.update received")
        return
    requested_model = _model_from_session_update(first_raw)
    if requested_model is None:
        logger.info("realtime connection rejected: first frame is not a session.update with model")
        await _safe_close_client(client, WS_POLICY_VIOLATION, "first frame must be session.update with model")
        return

    settings = get_settings()
    async with get_sessionmaker()() as s:
        result = await run_preflight(
            s, settings=settings, token=token, requested_model=requested_model
        )
        if isinstance(result, PreflightRejection):
            logger.info(
                "realtime preflight rejected model=%s code=%s", requested_model, result.code
            )
            await _safe_close_client(client, WS_POLICY_VIOLATION, result.code)
            return
        # Model must be a realtime kind (FR-007) — catalog honesty (FR-008).
        row = (
            await s.execute(select(ModelCatalog).where(ModelCatalog.slug == result.canonical_model))
        ).scalar_one_or_none()
        kind = model_kind(row) if row is not None else "chat"
        if kind != "realtime":
            logger.info(
                "realtime connection rejected: model=%s kind=%s (not realtime)",
                result.canonical_model, kind,
            )
            await _safe_close_client(client, WS_UNSUPPORTED, "model does not support realtime")
            return
        allocation_id = result.allocation.id
        subject = result.allocation.subject_snapshot

    resolved = result.resolved
    sess = RealtimeSession(
        allocation_id=allocation_id,
        subject=subject,
        resource_model=result.canonical_model,
        upstream_model=result.upstream_model,
        provider=result.provider,
        request_id=request_id,
        started_at=started_at,
    )
    # Meter the first frame too (it may already be an append in some clients).
    _meter_client_event(sess, first_raw)

    # Open the upstream provider WS; never leak key/endpoint to the client (FR-006).
    try:
        upstream = await open_upstream(
            provider=result.provider,
            model=result.upstream_model,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            api_version=(resolved.extra_config or {}).get("api_version"),
        )
    except Exception:
        logger.exception("realtime upstream connect failed model=%s", result.upstream_model)
        sess.close_reason = "upstream_error"
        await _safe_close_client(client, WS_INTERNAL, "upstream unavailable")
        await _bill_session(sess)
        return

    logger.info(
        "realtime connection open allocation=%s model=%s request_id=%s",
        allocation_id, result.canonical_model, request_id,
    )
    try:
        # Replay the first session.update to upstream so it configures correctly.
        try:
            await upstream.send(first_raw)
        except Exception:
            sess.close_reason = "upstream_error"
        else:
            await run_relay(
                client, upstream, sess, check_active=check_active, interval=revoke_interval
            )
    finally:
        await _safe_close_upstream(upstream)
        await _bill_session(sess)
        logger.info(
            "realtime connection closed allocation=%s reason=%s minutes=%s",
            allocation_id, sess.close_reason, session_minutes(sess),
        )


def _model_from_session_update(raw: str) -> str | None:
    try:
        ev = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(ev, dict) or ev.get("type") != "session.update":
        return None
    session = ev.get("session")
    if not isinstance(session, dict):
        return None
    model = session.get("model")
    return model if isinstance(model, str) and model else None


@router.websocket("/realtime")
async def realtime_endpoint(websocket: WebSocket) -> None:
    """OpenAI-compatible realtime transcription WS. Thin adapter: FastAPI's
    WebSocket satisfies the ClientWS interface; the real upstream opener is wired
    here (CI injects a fake via `handle_realtime`)."""
    from ai_api.proxy import upstream

    await handle_realtime(websocket, open_upstream=upstream.open_realtime_ws)
