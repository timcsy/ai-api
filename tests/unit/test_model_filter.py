"""Unit tests for catalog filter + facet pure functions (Phase 4 US1-US3)."""
from __future__ import annotations

from datetime import UTC, datetime

from ai_api.models import ModelCatalog
from ai_api.services.model_catalog import (
    FACET_DIMENSIONS,
    compute_facets,
    filter_models,
)


def _m(
    slug: str,
    *,
    family: str = "gpt-4",
    cost_tier: str = "medium",
    modality_input: list[str] | None = None,
    modality_output: list[str] | None = None,
    capabilities: list[str] | None = None,
    recommended_for: list[str] | None = None,
    tags: list[str] | None = None,
    context_window: int = 4096,
    status: str = "active",
    provider: str = "azure",
) -> ModelCatalog:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    return ModelCatalog(
        slug=slug,
        provider=provider,
        display_name=slug.split("/", 1)[-1],
        family=family,
        description="",
        modality_input=modality_input or ["text"],
        modality_output=modality_output or ["text"],
        capabilities=capabilities or [],
        context_window=context_window,
        cost_tier=cost_tier,
        recommended_for=recommended_for or [],
        tags=tags or [],
        example_request={},
        official_doc_url=None,
        status=status,
        deprecation_note=None,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# filter_models
# ---------------------------------------------------------------------------


def test_empty_filter_returns_all() -> None:
    models = [_m("a/x"), _m("a/y")]
    assert filter_models(models) == models


def test_filter_modality_output_image() -> None:
    a = _m("a/dalle", modality_output=["image"])
    b = _m("a/gpt", modality_output=["text"])
    out = filter_models([a, b], modality_output={"image"})
    assert out == [a]


def test_filter_capability_and_semantics() -> None:
    a = _m("a/gpt4o", capabilities=["vision", "function-calling"])
    b = _m("a/o1", capabilities=["reasoning"])
    c = _m("a/gpt4o-mini", capabilities=["vision"])
    out = filter_models(
        [a, b, c], capabilities={"vision", "function-calling"}
    )
    assert out == [a]  # only a has BOTH


def test_filter_cross_field_and() -> None:
    big = _m("a/gpt4o", capabilities=["vision"], cost_tier="high")
    small = _m("a/gpt4o-mini", capabilities=["vision"], cost_tier="low")
    out = filter_models([big, small], capabilities={"vision"}, cost_tier="low")
    assert out == [small]


def test_filter_case_insensitive() -> None:
    a = _m("a/gpt4o", modality_input=["text", "image"])
    out = filter_models([a], modality_input={"Image"})
    assert out == [a]


def test_filter_min_context_window() -> None:
    big = _m("a/big", context_window=200000)
    small = _m("a/small", context_window=8000)
    out = filter_models([big, small], min_context_window=128000)
    assert out == [big]


def test_filter_missing_capability_excludes() -> None:
    a = _m("a/x", capabilities=["chat"])
    out = filter_models([a], capabilities={"chat", "vision"})
    assert out == []


# ---------------------------------------------------------------------------
# compute_facets
# ---------------------------------------------------------------------------


def test_facets_empty_list_returns_stable_schema() -> None:
    out = compute_facets([])
    assert set(out.keys()) == set(FACET_DIMENSIONS)
    for dim in FACET_DIMENSIONS:
        assert out[dim] == {}


def test_facets_counts_correctly() -> None:
    models = [
        _m(
            "a/gpt4o",
            family="gpt-4",
            cost_tier="high",
            modality_input=["text", "image"],
            modality_output=["text"],
            capabilities=["chat", "vision"],
            recommended_for=["chat"],
            tags=["multimodal"],
        ),
        _m(
            "a/gpt4o-mini",
            family="gpt-4",
            cost_tier="low",
            modality_input=["text", "image"],
            modality_output=["text"],
            capabilities=["chat", "vision"],
            recommended_for=["chat", "agent"],
            tags=["multimodal", "cost-effective"],
        ),
        _m(
            "a/dalle",
            family="dall-e",
            cost_tier="high",
            modality_input=["text"],
            modality_output=["image"],
            capabilities=[],
            recommended_for=["image-gen"],
            tags=["image-generation"],
        ),
    ]
    facets = compute_facets(models)
    assert facets["modality_input"]["text"] == 3
    assert facets["modality_input"]["image"] == 2
    assert facets["modality_output"]["text"] == 2
    assert facets["modality_output"]["image"] == 1
    assert facets["capabilities"]["vision"] == 2
    assert facets["cost_tier"] == {"high": 2, "low": 1}
    assert facets["family"] == {"gpt-4": 2, "dall-e": 1}
    assert facets["recommended_for"]["chat"] == 2
    assert facets["recommended_for"]["agent"] == 1
    assert facets["tags"]["multimodal"] == 2


def test_facets_schema_stable_with_data() -> None:
    out = compute_facets([_m("a/x")])
    assert set(out.keys()) == set(FACET_DIMENSIONS)


def test_capability_vocab_canonicalized_merges_underscore_and_hyphen():
    # rev 76: function_calling vs function-calling must merge into ONE facet bucket
    models = [
        _m("azure/a", capabilities=["chat", "function-calling"]),
        _m("azure/b", capabilities=["chat", "function_calling"]),
    ]
    facets = compute_facets(models)
    caps = facets["capabilities"]
    assert caps.get("function-calling") == 2
    assert "function_calling" not in caps  # underscore variant folded in
    # filtering by the canonical value matches BOTH rows
    assert len(filter_models(models, capabilities=["function-calling"])) == 2
    # filtering by the underscore form also matches both (canonicalized)
    assert len(filter_models(models, capabilities=["function_calling"])) == 2
