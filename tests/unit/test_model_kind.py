"""Phase 26: model_kind — decide a model's test kind from litellm mode (primary)
or modality (fallback). Key trap: litellm maps embedding → output=["text"] (same
as chat), so chat↔embedding MUST be told apart by mode, not modality."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_api.services.model_kind import is_billable, is_supported, model_kind


def _m(*, mode=None, modality_input=None, modality_output=None):
    sync = {"raw": {"mode": mode}} if mode is not None else None
    return SimpleNamespace(
        litellm_sync=sync,
        modality_input=modality_input or ["text"],
        modality_output=modality_output or ["text"],
    )


# --- litellm mode takes priority ---
@pytest.mark.parametrize(
    "mode,expected",
    [
        ("chat", "chat"),
        ("completion", "chat"),
        ("embedding", "embedding"),
        ("image_generation", "image"),
        ("audio_speech", "tts"),
        ("audio_transcription", "stt"),
        ("rerank", "rerank"),
        ("moderation", "moderation"),
        ("search", "search"),
        ("image_edit", "image_edit"),
        ("video_generation", "unknown"),
    ],
)
def test_kind_by_litellm_mode(mode, expected):
    assert model_kind(_m(mode=mode)) == expected


def test_embedding_vs_chat_collision_resolved_by_mode():
    # both have modality_output text; only mode tells them apart
    assert model_kind(_m(mode="embedding", modality_output=["text"])) == "embedding"
    assert model_kind(_m(mode="chat", modality_output=["text"])) == "chat"


# --- modality fallback (manual model, no litellm_sync) ---
def test_fallback_image_by_output():
    assert model_kind(_m(modality_output=["image"])) == "image"


def test_fallback_tts_by_output_audio():
    assert model_kind(_m(modality_output=["audio"])) == "tts"


def test_fallback_stt_by_input_audio():
    assert model_kind(_m(modality_input=["audio"], modality_output=["text"])) == "stt"


def test_fallback_text_defaults_to_chat():
    # manual embedding (no mode) unavoidably falls to chat — known limitation
    assert model_kind(_m(modality_output=["text"])) == "chat"


def test_sync_without_raw_or_mode_falls_back():
    # litellm_sync present but no raw/mode → modality fallback, no crash
    m = SimpleNamespace(litellm_sync={"base_model_key": "x"}, modality_input=["text"], modality_output=["image"])
    assert model_kind(m) == "image"


def test_always_returns_one_of_six():
    for m in [_m(mode="chat"), _m(mode="zzz"), _m(modality_output=["audio"]), _m()]:
        assert model_kind(m) in {"chat", "embedding", "tts", "image", "stt", "unknown"}


# --- helpers ---
def test_is_billable():
    # binary/document + media-generating kinds cost real money on a minimal test
    for k in ("image", "tts", "ocr", "stt", "image_edit", "search"):
        assert is_billable(k)
    for k in ("chat", "embedding", "moderation", "rerank", "unknown"):
        assert not is_billable(k)


def test_is_supported():
    # auto-testable IFF a recipe exists (model_test.RECIPES). Every inference kind
    # now has a real recipe (ocr/stt/image_edit/search send a minimal fixture).
    for k in ("chat", "embedding", "tts", "image", "moderation", "rerank",
              "ocr", "stt", "search", "image_edit", "realtime"):
        assert is_supported(k)
    # only 'unknown' has no recipe → honestly not auto-testable (never a fake pass)
    assert not is_supported("unknown")


# --- Phase 32: realtime is a CAPABILITY (supported_endpoints / admin marker), not a mode ---
def _cap(*, mode=None, supported_endpoints=None, capabilities=None):
    raw = {}
    if mode is not None:
        raw["mode"] = mode
    if supported_endpoints is not None:
        raw["supported_endpoints"] = supported_endpoints
    return SimpleNamespace(
        litellm_sync={"raw": raw} if raw else None,
        modality_input=["audio"], modality_output=["text"],
        capabilities=capabilities or [],
    )


def test_realtime_from_supported_endpoints_overrides_stt():
    # gpt-realtime-whisper: litellm mode=audio_transcription but /v1/realtime in
    # supported_endpoints → realtime (capability beats the audio_transcription→stt map).
    m = _cap(mode="audio_transcription",
             supported_endpoints=["/v1/realtime", "/v1/realtime/transcription_sessions"])
    assert model_kind(m) == "realtime"


def test_realtime_from_admin_marker():
    # Manual model (no litellm_sync): admin marks the `realtime` capability.
    m = _cap(capabilities=["realtime"])
    assert model_kind(m) == "realtime"


def test_realtime_blocked_marker_forces_off():
    m = _cap(mode="audio_transcription", supported_endpoints=["/v1/realtime"],
             capabilities=["realtime:blocked"])
    assert model_kind(m) == "stt"  # admin override wins → falls back to mode


def test_plain_transcription_stays_stt():
    # whisper-1: audio_transcription, NO /v1/realtime → batch STT, not realtime.
    m = _cap(mode="audio_transcription")
    assert model_kind(m) == "stt"
