"""Model catalog service — pure functions for filter + facet computation.

Per research.md §1+§2+§6:
- list-valued fields stored as JSON; filter is in-Python set operations
- AND semantics for list filters (subset check)
- facet schema is stable (dimension keys hard-coded)
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_api.models import ModelCatalog
from ai_api.services import responses_support

# Enum sets used by both Pydantic schema and filter validation.
MODALITY_VALUES = ("text", "image", "audio", "video", "embedding")
CAPABILITY_VALUES = (
    "chat",
    "vision",
    "function-calling",
    "json-mode",
    "tool-use",
    "streaming",
    "reasoning",
    "embedding",
    "fine-tuning",
    "responses",
)
COST_TIER_VALUES = ("low", "medium", "high")
STATUS_VALUES = ("active", "preview", "deprecated")


# ---------------------------------------------------------------------------
# Pydantic schema for YAML loading
# ---------------------------------------------------------------------------

Modality = Literal["text", "image", "audio", "video", "embedding"]
Capability = Literal[
    "chat",
    "vision",
    "function-calling",
    "json-mode",
    "tool-use",
    "streaming",
    "reasoning",
    "embedding",
    "fine-tuning",
    "responses",
]
CostTier = Literal["low", "medium", "high"]
Status = Literal["active", "preview", "deprecated"]


DefaultAccessLit = Literal["open", "restricted"]


class ModelEntry(BaseModel):
    """YAML schema for one model entry (research.md §4)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(pattern=r"^[a-z0-9-]+/[a-z0-9.-]+$")
    provider: str
    display_name: str
    family: str
    description: str
    modality_input: list[Modality]
    modality_output: list[Modality]
    capabilities: list[Capability]
    context_window: int = Field(ge=0)
    cost_tier: CostTier
    recommended_for: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    example_request: dict[str, Any]
    official_doc_url: str | None = None
    status: Status = "active"
    deprecation_note: str | None = None
    # Phase 5: access policy — default_access REQUIRED, tag lists default to [].
    default_access: DefaultAccessLit
    allowed_tags: list[str] = Field(default_factory=list)
    denied_tags: list[str] = Field(default_factory=list)


class CatalogYAML(BaseModel):
    """Top-level YAML schema."""

    model_config = ConfigDict(extra="forbid")

    models: list[ModelEntry]


# ---------------------------------------------------------------------------
# Filter — pure function
# ---------------------------------------------------------------------------


def _lower_set(values: Iterable[str] | None) -> set[str] | None:
    if values is None:
        return None
    return {v.strip().lower() for v in values if v.strip()}


def canon_capability(v: str) -> str:
    """Canonicalize capability vocab so the underscore/hyphen variants merge
    (function_calling == function-calling, prompt_caching == prompt-caching).
    litellm emits hyphenated, but older/hand-entered rows used underscores —
    canonicalizing at the facet/filter layer collapses the duplicate buckets."""
    return v.strip().lower().replace("_", "-")


def filter_models(
    models: list[ModelCatalog],
    *,
    capabilities: Iterable[str] | None = None,
    modality_input: Iterable[str] | None = None,
    modality_output: Iterable[str] | None = None,
    recommended_for: Iterable[str] | None = None,
    tags: Iterable[str] | None = None,
    cost_tier: str | None = None,
    provider: str | None = None,
    family: str | None = None,
    min_context_window: int | None = None,
) -> list[ModelCatalog]:
    """Filter models per spec FR-007 AND semantics."""
    caps = {canon_capability(c) for c in capabilities} if capabilities is not None else None
    mi = _lower_set(modality_input)
    mo = _lower_set(modality_output)
    rec = _lower_set(recommended_for)
    tagset = _lower_set(tags)
    ct = cost_tier.strip().lower() if cost_tier else None
    pv = provider.strip().lower() if provider else None
    fam = family.strip().lower() if family else None

    def matches(m: ModelCatalog) -> bool:
        if caps and not caps.issubset({canon_capability(c) for c in m.capabilities}):
            return False
        if mi and not mi.issubset({v.lower() for v in m.modality_input}):
            return False
        if mo and not mo.issubset({v.lower() for v in m.modality_output}):
            return False
        if rec and not rec.issubset({v.lower() for v in m.recommended_for}):
            return False
        if tagset and not tagset.issubset({v.lower() for v in m.tags}):
            return False
        if ct and m.cost_tier.lower() != ct:
            return False
        if pv and m.provider.lower() != pv:
            return False
        if fam and m.family.lower() != fam:
            return False
        return not (
            min_context_window is not None and m.context_window < min_context_window
        )

    return [m for m in models if matches(m)]


# ---------------------------------------------------------------------------
# Facet computation — pure function
# ---------------------------------------------------------------------------

FACET_DIMENSIONS = (
    "modality_input",
    "modality_output",
    "capabilities",
    "cost_tier",
    "recommended_for",
    "family",
    "tags",
)


def compute_facets(models: list[ModelCatalog]) -> dict[str, dict[str, int]]:
    """Faceted counts per dimension. Schema stable: all dimension keys always present."""
    out: dict[str, dict[str, int]] = {dim: defaultdict(int) for dim in FACET_DIMENSIONS}
    for m in models:
        for v in m.modality_input:
            out["modality_input"][v] += 1
        for v in m.modality_output:
            out["modality_output"][v] += 1
        # Phase 25: hide internal responses:* markers from member-facing facets;
        # the bare `responses` value (= "Agent 相容") is kept and filterable.
        # Canonicalize vocab so function_calling/function-calling merge into one
        # bucket (else the facet shows two "函式呼叫" rows).
        for v in responses_support.strip_internal(m.capabilities):
            out["capabilities"][canon_capability(v)] += 1
        out["cost_tier"][m.cost_tier] += 1
        for v in m.recommended_for:
            out["recommended_for"][v] += 1
        out["family"][m.family] += 1
        for v in m.tags:
            out["tags"][v] += 1
    return {k: dict(v) for k, v in out.items()}
