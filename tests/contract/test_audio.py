"""Phase 29 ③ (041) US3+US4: contract tests for /v1/audio/speech (TTS) and
/v1/audio/transcriptions (STT).

TTS: binary audio OUTPUT, billed per CHARACTER. STT: multipart audio INPUT,
billed as tokens. Upstream litellm functions are mocked.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord, PriceList

TTS = "tts-1"
STT = "gpt-4o-transcribe"


async def _alloc(client: AsyncClient, admin_headers: dict[str, str], model: str) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


class _Bin:
    """Stand-in for litellm HttpxBinaryResponseContent."""
    def __init__(self, content: bytes) -> None:
        self.content = content


async def _seed_char_price(per_char: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider="azure", model=TTS,
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="character", price_per_unit_usd=Decimal(per_char),
            effective_from=datetime.now(UTC) - timedelta(days=1),
            created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()


async def _last(outcome: CallOutcome) -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == outcome)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


# ---------------------------------------------------------------- TTS

@pytest.mark.asyncio
async def test_tts_returns_audio_billed_per_char(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers, TTS)
    await _seed_char_price("0.0001")
    text = "hello world"  # 11 chars
    with patch("ai_api.proxy.upstream.aspeech", new=AsyncMock(return_value=_Bin(b"AUDIO"))):
        r = await app_client.post(
            "/v1/audio/speech", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": TTS, "input": text, "voice": "alloy"},
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("audio/")
    assert r.content == b"AUDIO"
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "character" and rec.quantity == 11
    assert rec.cost_usd == Decimal("0.0011")  # 11 x 0.0001
    assert rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_tts_400_missing_input(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers, TTS)
    r = await app_client.post(
        "/v1/audio/speech", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": TTS, "voice": "alloy"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_tts_upstream_error_json(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers, TTS)
    with patch("ai_api.proxy.upstream.aspeech", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await app_client.post(
            "/v1/audio/speech", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": TTS, "input": "hi", "voice": "alloy"},
        )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "upstream_error"  # error path is JSON
    rec = await _last(CallOutcome.upstream_error)
    assert rec is not None


# ---------------------------------------------------------------- STT

@pytest.mark.asyncio
async def test_stt_multipart_billed_tokens(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers, STT)
    stub = {"text": "hello", "usage": {"prompt_tokens": 4, "total_tokens": 4}}
    with patch("ai_api.proxy.upstream.atranscription", new=AsyncMock(return_value=stub)):
        r = await app_client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            data={"model": STT},
            files={"file": ("a.mp3", b"AUDIOBYTES", "audio/mpeg")},
        )
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "hello"
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.prompt_tokens == 4 and rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_stt_400_missing_file(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers, STT)
    r = await app_client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        data={"model": STT},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_stt_401(app_client: AsyncClient) -> None:
    r = await app_client.post(
        "/v1/audio/transcriptions",
        data={"model": STT}, files={"file": ("a.mp3", b"x", "audio/mpeg")},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stt_upstream_error(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers, STT)
    with patch("ai_api.proxy.upstream.atranscription", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await app_client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            data={"model": STT}, files={"file": ("a.mp3", b"x", "audio/mpeg")},
        )
    assert r.status_code == 502
    rec = await _last(CallOutcome.upstream_error)
    assert rec is not None
