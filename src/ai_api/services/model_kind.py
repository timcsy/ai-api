"""Phase 26: decide what KIND of test to run for a catalog model.

A model's testable kind drives which minimal upstream call the admin "test model"
action makes. Detection prefers the litellm `mode` (carried in the existing
``litellm_sync["raw"]["mode"]``, Phase 24) and falls back to modality for
hand-entered models (no litellm_sync).

Trap: ``litellm_registry._modality`` maps embedding → output ``["text"]`` — the
SAME shape as chat — so chat vs embedding can ONLY be told apart by mode. A manual
embedding model (no mode) unavoidably falls to ``chat``; the chat test then fails
naturally and gives an identifiable signal (not a silent misclassification).
"""
from __future__ import annotations

from typing import Any, Literal

Kind = Literal[
    "chat", "embedding", "tts", "image", "stt", "ocr", "rerank",
    "moderation", "search", "image_edit", "realtime", "unknown",
]

# litellm mode → our kind
_MODE_TO_KIND: dict[str, Kind] = {
    "chat": "chat",
    "completion": "chat",
    "embedding": "embedding",
    "image_generation": "image",
    "audio_speech": "tts",
    "audio_transcription": "stt",
    "ocr": "ocr",
    "rerank": "rerank",
    "moderation": "moderation",
    "search": "search",
    "image_edit": "image_edit",
    # Phase 32: live transcription over WebSocket (gpt-realtime-whisper). Not a
    # recipe-table "test model" kind — billed per-minute via the /v1/realtime relay.
    "realtime": "realtime",
}


def _mode_of(model: Any) -> str | None:
    sync = getattr(model, "litellm_sync", None)
    if not isinstance(sync, dict):
        return None
    raw = sync.get("raw")
    if not isinstance(raw, dict):
        return None
    mode = raw.get("mode")
    return mode if isinstance(mode, str) else None


def model_kind(model: Any) -> Kind:
    """Decide the testable kind of a catalog model. Never raises; always one of Kind."""
    mode = _mode_of(model)
    if mode is not None:
        # known mode → mapped kind; any other litellm mode → unsupported
        return _MODE_TO_KIND.get(mode, "unknown")

    # Fallback: hand-entered models have no litellm_sync → use modality.
    out = list(getattr(model, "modality_output", None) or [])
    inp = list(getattr(model, "modality_input", None) or [])
    if out == ["image"]:
        return "image"
    if out == ["audio"]:
        return "tts"
    if "audio" in inp:
        return "stt"
    # text output (incl. manual embedding, which we can't distinguish from chat)
    return "chat"


def is_billable(kind: str) -> bool:
    """Whether the minimal auto-test costs real money. Derived from the test-recipe
    table (the single source of truth) so it can't drift from what's actually run."""
    from ai_api.services.model_test import is_billable as _is_billable
    return _is_billable(kind)


def is_supported(kind: str) -> bool:
    """Whether this kind can be auto-tested — IFF a test recipe exists for it.
    Derived from the recipe table, so adding a kind without a recipe is honestly
    'unsupported', never a silent fake pass."""
    from ai_api.services.model_test import is_testable
    return is_testable(kind)
