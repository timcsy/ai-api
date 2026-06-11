"""Phase 31: price_from_entry surfaces non-token unit suggestions (OCR per-page, etc.)
so admin can one-click adopt them — previously returned None for non-token models."""
from __future__ import annotations

from ai_api.services.litellm_registry import price_from_entry


def test_token_entry_unchanged():
    p = price_from_entry({"input_cost_per_token": 5e-06, "output_cost_per_token": 1e-05})
    assert p is not None and p["input_per_1k"] == "0.005"
    assert "price_unit" not in p


def test_ocr_per_page_suggestion():
    p = price_from_entry({"mode": "ocr", "ocr_cost_per_page": 0.003})
    assert p is not None
    assert p["price_unit"] == "page" and p["price_per_unit"] == "0.003"
    assert p["input_per_1k"] == "0"


def test_rerank_per_query_suggestion():
    p = price_from_entry({"mode": "rerank", "input_cost_per_query": 0.002})
    assert p is not None and p["price_unit"] == "query" and p["price_per_unit"] == "0.002"


def test_tts_per_character_suggestion():
    p = price_from_entry({"mode": "audio_speech", "input_cost_per_character": 1.5e-05})
    assert p is not None and p["price_unit"] == "character"


def test_token_takes_precedence_over_image():
    # azure gpt-image has both token + per-image keys → token wins
    p = price_from_entry({"input_cost_per_token": 5e-06, "output_cost_per_image": 0.04})
    assert p is not None and "price_unit" not in p


def test_no_cost_returns_none():
    assert price_from_entry({"mode": "chat"}) is None
