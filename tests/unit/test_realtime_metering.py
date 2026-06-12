"""Phase 32 (043) T014: realtime per-minute metering — PCM bytes → minutes.

Pure functions; no DB, no WS. The duration source is the audio WE relayed (Σ append
PCM bytes), not a provider usage event (research R2), so an abnormal abort still
yields a correct billable quantity.
"""
from __future__ import annotations

from ai_api.proxy.realtime import (
    RealtimeSession,
    duration_seconds,
    pcm_bytes_to_minutes,
    pcm_bytes_to_seconds,
    session_minutes,
    session_quantity,
)


def test_duration_seconds_pcm16_mono() -> None:
    # 24000 Hz x 2 bytes x 1 ch = 48000 bytes/sec -> 1 second.
    assert duration_seconds(48000, 24000, 2, 1) == 1.0
    # half a second
    assert duration_seconds(24000, 24000, 2, 1) == 0.5
    # unknown geometry → 0 (never divide by zero)
    assert duration_seconds(48000, 0, 2, 1) == 0.0


def test_minutes_round_up_started_minute_is_billed() -> None:
    rate = 24000  # pcm16 mono → 48000 bytes/sec
    per_sec = rate * 2 * 1
    assert pcm_bytes_to_minutes(0) == 0                       # nothing → 0
    assert pcm_bytes_to_minutes(per_sec) == 1                 # 1s → 1 min (round up)
    assert pcm_bytes_to_minutes(per_sec * 59) == 1            # 59s → 1 min
    assert pcm_bytes_to_minutes(per_sec * 60) == 1            # exactly 60s → 1 min
    assert pcm_bytes_to_minutes(per_sec * 61) == 2            # 61s → 2 min
    assert pcm_bytes_to_minutes(per_sec * 300) == 5           # 5 min exact


def test_minutes_respects_session_geometry() -> None:
    # 16 kHz pcm16 mono = 32000 bytes/sec; 96000 bytes = 3s → 1 min
    assert pcm_bytes_to_minutes(96000, sample_rate=16000) == 1


def test_seconds_round_up() -> None:
    rate = 24000
    per_sec = rate * 2 * 1  # 48000 bytes/sec
    assert pcm_bytes_to_seconds(0) == 0
    assert pcm_bytes_to_seconds(per_sec) == 1
    assert pcm_bytes_to_seconds(per_sec // 2) == 1          # 0.5s -> 1s (round up)
    assert pcm_bytes_to_seconds(per_sec * 10) == 10
    assert pcm_bytes_to_seconds(per_sec * 10 + 1) == 11     # a started second is billed


def _sess(rate: int = 24000) -> RealtimeSession:
    from datetime import UTC, datetime

    return RealtimeSession(
        allocation_id="a", subject="s", resource_model="azure/gpt-realtime-whisper",
        upstream_model="azure/gpt-realtime-whisper", provider="azure",
        request_id="r", started_at=datetime.now(UTC), sample_rate=rate,
    )


def test_session_minutes_uses_session_state() -> None:
    sess = _sess(16000)
    sess.audio_bytes = 32000 * 90  # 90 seconds at 16 kHz pcm16 mono
    assert session_minutes(sess) == 2  # 90s → 2 min


def test_session_quantity_follows_price_unit() -> None:
    sess = _sess(24000)
    sess.audio_bytes = 24000 * 2 * 10  # 10 seconds
    assert session_quantity(sess, "second") == 10
    assert session_quantity(sess, "minute") == 1      # 10s → 1 min (round up)
    # any non-minute unit (incl. unknown) bills in seconds
    assert session_quantity(sess, "anything-else") == 10
