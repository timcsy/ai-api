"""Phase 32 (043): /v1/realtime contract tests (contracts/realtime-transcription.md 1-7).

Drives `handle_realtime` in-loop with a fake client WS + fake provider WS (the
engine is bound to the test loop, so a TestClient portal would break the DB). This
is the Constitution-Deviation remedy: CI exercises the full preflight → relay →
metering → revocation path against a mock provider WS; real Azure WS is the
maintainer's T027 smoke.

Covers: T007 (invalid/revoked key → close, no stream), T008 (non-realtime →
unsupported), T009 (valid → delta), T015 (clean close → CallRecord minute), T016
(abnormal abort → billed), T020/T021 (in-flight revoke/pause → close + billed),
plus the no-leak contract (#7).
"""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord, ModelCatalog, PriceList
from ai_api.proxy.realtime import handle_realtime
from tests.support.realtime_mock import FakeClientWS, FakeUpstreamWS, fake_opener

RT_MODEL = "azure/gpt-realtime-whisper"
# The resolved upstream credential — must never reach the downstream client (FR-006).
SECRET_KEY = "az-secret-DO-NOT-LEAK-9999"
SECRET_BASE = "https://secret-foundry.services.ai.azure.com"

# 24 kHz pcm16 mono → 48000 bytes/sec.
_BYTES_PER_SEC = 24000 * 2 * 1


def _session_update(model: str = RT_MODEL, rate: int = 24000) -> str:
    return json.dumps({
        "type": "session.update",
        "session": {
            "type": "transcription",
            "model": model,
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": rate}}},
        },
    })


def _append(seconds: float, rate: int = 24000) -> str:
    pcm = b"\x00" * int(_BYTES_PER_SEC * seconds * (rate / 24000))
    return json.dumps({
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm).decode(),
    })


async def _seed_catalog(slug: str, *, mode: str = "audio_transcription", realtime: bool = True) -> None:
    """Seed a catalog row. Realtime models mirror litellm reality (PR #29775):
    mode=audio_transcription + supported_endpoints listing /v1/realtime — the
    capability axis that drives model_kind → realtime (NOT a litellm 'realtime' mode)."""
    now = datetime.now(UTC)
    raw: dict = {"mode": mode}
    if realtime:
        raw["supported_endpoints"] = ["/v1/realtime", "/v1/realtime/transcription_sessions"]
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider="azure", display_name=slug, family="x",
            description="", modality_input=["audio"], modality_output=["text"],
            capabilities=[], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
            litellm_sync={"raw": raw},
        ))
        await s.commit()


async def _seed_price(per_minute: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider="azure", model="gpt-realtime-whisper",
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="minute", price_per_unit_usd=Decimal(per_minute),
            effective_from=datetime.now(UTC) - timedelta(days=1),
            created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()


async def _seed_provider(client: AsyncClient, admin: dict) -> None:
    """An active provider credential is required for preflight's model-access check
    to pass (env fallback doesn't register as an active provider)."""
    r = await client.post("/admin/providers", headers=admin, json={
        "provider": "azure", "label": "t", "api_key": SECRET_KEY, "base_url": SECRET_BASE,
    })
    assert r.status_code in (200, 201), r.text


async def _alloc(client: AsyncClient, admin: dict, model: str = RT_MODEL) -> dict:
    r = await client.post("/admin/allocations", headers=admin,
                          json={"subject": "alice@example.com", "resource_model": model})
    assert r.status_code == 201, r.text
    return r.json()


async def _last(outcome: CallOutcome) -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == outcome)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


def _bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


# --- T007: invalid / revoked key → close, no stream -------------------------
@pytest.mark.asyncio
async def test_invalid_key_closed_no_stream(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    client = FakeClientWS(_bearer("totally-invalid-token"), [_session_update()])
    upstream = FakeUpstreamWS()
    opener = fake_opener(upstream)
    await handle_realtime(client, open_upstream=opener)
    assert client.closed is not None and client.closed[0] == 1008  # policy violation
    assert opener.calls == []           # upstream never opened
    assert upstream.sent == []          # no stream started
    assert await _last(CallOutcome.success) is None


@pytest.mark.asyncio
async def test_missing_bearer_closed(app_client: AsyncClient, admin_headers):
    client = FakeClientWS({}, [_session_update()])
    opener = fake_opener(FakeUpstreamWS())
    await handle_realtime(client, open_upstream=opener)
    assert client.closed is not None and client.closed[0] == 1008
    assert opener.calls == []


@pytest.mark.asyncio
async def test_revoked_allocation_closed(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    alloc = await _alloc(app_client, admin_headers)
    # Revoke it before connecting.
    r = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    assert r.status_code in (200, 204), r.text
    client = FakeClientWS(_bearer(alloc["token"]), [_session_update()])
    opener = fake_opener(FakeUpstreamWS())
    await handle_realtime(client, open_upstream=opener)
    assert client.closed is not None and client.closed[0] == 1008
    assert opener.calls == []


# --- T008: non-realtime model → close(unsupported) --------------------------
@pytest.mark.asyncio
async def test_non_realtime_model_unsupported(app_client: AsyncClient, admin_headers):
    chat_model = "azure/gpt-4o-mini"
    await _seed_catalog(chat_model, mode="chat", realtime=False)
    await _seed_provider(app_client, admin_headers)
    alloc = await _alloc(app_client, admin_headers, model=chat_model)
    client = FakeClientWS(_bearer(alloc["token"]), [_session_update(model=chat_model)])
    opener = fake_opener(FakeUpstreamWS())
    await handle_realtime(client, open_upstream=opener)
    assert client.closed is not None and client.closed[0] == 1003  # unsupported
    assert opener.calls == []


# --- T009: valid connection + append → delta reaches client -----------------
@pytest.mark.asyncio
async def test_valid_connection_relays_delta(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    delta = json.dumps({
        "type": "conversation.item.input_audio_transcription.delta", "delta": "hello",
    })
    completed = json.dumps({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "hello world",
    })
    # Upstream drives the end: emit delta+completed then hang up.
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(1.0)], hold_open=True)
    upstream = FakeUpstreamWS([delta, completed], close_after=True)
    opener = fake_opener(upstream)
    await handle_realtime(client, open_upstream=opener)
    assert any("transcription.delta" in m for m in client.sent), client.sent
    # The session.update + append were forwarded upstream (key/endpoint injected
    # on the upstream side, never to the client).
    assert opener.calls and opener.calls[0]["model"] == RT_MODEL
    assert any("input_audio_buffer.append" in m for m in upstream.sent)


# --- T015: clean close → one CallRecord(unit=minute), quantity matches ------
@pytest.mark.asyncio
async def test_clean_close_bills_one_minute_record(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    await _seed_price("0.017")
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    # 90 seconds of audio → ceil(90/60) = 2 minutes. Client ends (disconnect).
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(90.0)], hold_open=False)
    upstream = FakeUpstreamWS(close_after=False)
    await handle_realtime(client, open_upstream=fake_opener(upstream))
    rec = await _last(CallOutcome.success)
    assert rec is not None
    assert rec.unit == "minute" and rec.quantity == 2
    assert rec.allocation_id == alloc["id"]
    assert rec.cost_usd == Decimal("0.034")  # 2 x 0.017
    assert rec.prompt_tokens is None and rec.total_tokens is None  # non-token call


@pytest.mark.asyncio
async def test_unpriced_realtime_defaults_to_seconds(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(30.0)], hold_open=False)
    await handle_realtime(client, open_upstream=fake_opener(FakeUpstreamWS(close_after=False)))
    rec = await _last(CallOutcome.success)
    # unpriced → default to litellm's native unit (second); 30s → 30
    assert rec is not None and rec.unit == "second" and rec.quantity == 30
    assert rec.cost_usd is None  # no PriceList → unpriced (NULL), not a crash


@pytest.mark.asyncio
async def test_per_second_price_billed_in_seconds(app_client: AsyncClient, admin_headers):
    """litellm prices gpt-realtime-whisper per SECOND — bill in seconds so the cost
    lines up with the imported per-unit price (input_cost_per_second)."""
    await _seed_catalog(RT_MODEL)
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider="azure", model="gpt-realtime-whisper",
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="second", price_per_unit_usd=Decimal("0.0002833"),
            effective_from=datetime.now(UTC) - timedelta(days=1),
            created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(10.0)], hold_open=False)
    await handle_realtime(client, open_upstream=fake_opener(FakeUpstreamWS(close_after=False)))
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "second" and rec.quantity == 10
    assert rec.cost_usd == Decimal("0.002833")  # 10 x 0.0002833


# --- T016: abnormal abort (client hangs up mid-stream) → accrued bytes billed
@pytest.mark.asyncio
async def test_abnormal_abort_still_bills_accrued(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    await _seed_price("0.017")
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    # Sends 45s then the client connection drops with no graceful close.
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(45.0)], hold_open=False)
    await handle_realtime(client, open_upstream=fake_opener(FakeUpstreamWS(close_after=False)))
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "minute" and rec.quantity == 1  # ceil(45/60)


# --- T020/T021: in-flight revoke / pause → close(revoked) within N + billed -
@pytest.mark.asyncio
async def test_inflight_revoke_closes_and_bills(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    await _seed_price("0.017")
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(30.0)], hold_open=True)
    upstream = FakeUpstreamWS(close_after=False)

    calls = {"n": 0}

    async def revoke_after_first_tick(allocation_id: str) -> bool:
        calls["n"] += 1
        return calls["n"] < 1  # first re-check already reports inactive

    await asyncio.wait_for(
        handle_realtime(
            client, open_upstream=fake_opener(upstream),
            check_active=revoke_after_first_tick, revoke_interval=0.05,
        ),
        timeout=5,
    )
    assert client.closed is not None and client.closed[0] == 1008
    assert client.closed[1] == "allocation revoked"
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "minute" and rec.quantity == 1
    assert rec.error_message == "allocation revoked mid-connection"


# --- Contract #7: no upstream key / endpoint ever reaches the client --------
@pytest.mark.asyncio
async def test_no_key_or_endpoint_leak(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    err = json.dumps({"type": "error", "error": {"code": "bad", "message": "upstream boom"}})
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(1.0)], hold_open=True)
    upstream = FakeUpstreamWS([err], close_after=True)
    await handle_realtime(client, open_upstream=fake_opener(upstream))
    blob = " ".join(client.sent) + " " + json.dumps(client.closed)
    assert SECRET_KEY not in blob
    assert "secret-foundry.services.ai.azure.com" not in blob


@pytest.mark.asyncio
async def test_upstream_connect_failure_no_leak_and_bills_zero(app_client: AsyncClient, admin_headers):
    await _seed_catalog(RT_MODEL)
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)

    async def failing_opener(**kwargs):
        raise RuntimeError(f"connect to {kwargs.get('api_base')} with {kwargs.get('api_key')} failed")

    client = FakeClientWS(_bearer(alloc["token"]), [_session_update(), _append(1.0)])
    await handle_realtime(client, open_upstream=failing_opener)
    assert client.closed is not None and client.closed[0] == 1011  # internal
    blob = json.dumps(client.closed) + " ".join(client.sent)
    assert SECRET_KEY not in blob and "secret-foundry.services.ai.azure.com" not in blob
    # Connect failed before any audio relayed → 0 (unpriced → default unit second).
    rec = await _last(CallOutcome.upstream_error)
    assert rec is not None and rec.unit == "second" and rec.quantity == 0


# --- Phase 33 (046) US2: in-connection cost-cap → close + bill --------------
@pytest.mark.asyncio
async def test_inflight_cost_cap_closes_and_bills(app_client: AsyncClient, admin_headers):
    """A realtime connection whose accrued cost crosses the monthly cap is closed
    mid-stream (policy violation) and the accrued time is still billed."""
    await _seed_catalog(RT_MODEL)
    await _seed_price("0.017")
    alloc = await _alloc(app_client, admin_headers)
    await _seed_provider(app_client, admin_headers)
    client = FakeClientWS(_bearer(alloc["token"]),
                          [_session_update(), _append(30.0)], hold_open=True)
    upstream = FakeUpstreamWS(close_after=False)

    ticks = {"n": 0}

    async def over_cost_after_first_tick(sess) -> bool:
        ticks["n"] += 1
        return ticks["n"] >= 1  # first re-check already reports over the cost cap

    await asyncio.wait_for(
        handle_realtime(
            client, open_upstream=fake_opener(upstream),
            over_cost=over_cost_after_first_tick, revoke_interval=0.05,
        ),
        timeout=5,
    )
    assert client.closed is not None and client.closed[0] == 1008
    assert client.closed[1] == "monthly cost cap reached"
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "minute" and rec.quantity == 1
    assert rec.error_message == "monthly cost cap reached mid-connection"
