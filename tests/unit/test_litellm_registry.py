"""Phase 23: litellm_registry adapter — maps litellm's bundled registry onto our
catalog fields. Asserts against real bundled values (pinned to the package)."""
from __future__ import annotations

from decimal import Decimal

from ai_api.services import litellm_registry as reg


def test_lookup_maps_metadata() -> None:
    meta = reg.lookup("azure/gpt-4o")
    assert meta is not None
    assert meta["context_window"] == 128000
    assert "text" in meta["modality_input"] and "image" in meta["modality_input"]  # vision
    assert "function_calling" in meta["capabilities"]


def test_suggest_price_converts_per_token_to_per_1k() -> None:
    price = reg.suggest_price("azure/gpt-4o")
    assert price is not None
    # litellm input_cost_per_token 2.5e-6 → per-1k 0.0025
    assert Decimal(price["input_per_1k"]) == Decimal("0.0025")
    assert Decimal(price["output_per_1k"]) == Decimal("0.01")
    assert price["cached_input_per_1k"] is not None


def test_lookup_unknown_key_returns_none() -> None:
    assert reg.lookup("totally/not-a-real-model-xyz") is None
    assert reg.suggest_price("totally/not-a-real-model-xyz") is None


def test_search_finds_by_substring_and_respects_limit() -> None:
    results = reg.search("gpt-4o", limit=5)
    assert len(results) <= 5
    assert any(r["key"] == "azure/gpt-4o" for r in results)
    hit = next(r for r in results if r["key"] == "azure/gpt-4o")
    assert hit["context_window"] == 128000 and hit["suggested_price"] is not None


def test_metadata_from_entry_image_generation() -> None:
    meta = reg.metadata_from_entry({"mode": "image_generation", "max_tokens": 4096})
    assert meta["modality_output"] == ["image"]


def test_current_version_nonempty() -> None:
    assert reg.current_version()  # truthy package version string
