"""Phase 29 ③ (041) US5: catalog honesty — non-chat models must not be faked as
chat. `_capabilities` no longer bottoms out to ["chat"] for non-chat modes."""
from __future__ import annotations

from ai_api.services.litellm_registry import _capabilities


def test_non_chat_no_flags_is_empty() -> None:
    # OCR / embedding / rerank entries with no chat-style flags → [] (honest)
    assert _capabilities({"mode": "ocr"}) == []
    assert _capabilities({"mode": "embedding"}) == []
    assert _capabilities({"mode": "rerank"}) == []
    assert _capabilities({"mode": "audio_speech"}) == []
    assert _capabilities({"mode": "image_generation"}) == []


def test_chat_modes_still_get_chat() -> None:
    # zero regression: chat-able modes keep "chat"
    assert "chat" in _capabilities({"mode": "chat"})
    assert "chat" in _capabilities({"mode": "completion"})
    assert "chat" in _capabilities({"mode": "responses"})
    # default (no mode) is treated as chat
    assert "chat" in _capabilities({})


def test_flags_still_mapped() -> None:
    caps = _capabilities({"mode": "chat", "supports_function_calling": True, "supports_vision": True})
    assert "chat" in caps and "function-calling" in caps and "vision" in caps


def test_non_chat_with_flags_keeps_flags_not_chat() -> None:
    # a non-chat model that happens to support vision → keeps vision, NOT chat
    caps = _capabilities({"mode": "image_generation", "supports_vision": True})
    assert "vision" in caps and "chat" not in caps
