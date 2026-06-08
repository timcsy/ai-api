"""Phase 23: adapter over LiteLLM's built-in model registry.

LiteLLM ships a registry (`litellm.model_cost`, ~2776 models) with context
windows, modality/capability flags and public list prices. This module is the
single place that reads it and maps it onto our catalog's fields, so a litellm
version bump only touches here.

Two sources:
- bundled (`litellm.model_cost`) — pinned to the installed package, read from
  memory, offline-safe. Used for create-time bring-in and search.
- live (`litellm.model_cost_map_url`, GitHub raw) — fetched only by the admin
  "check updates" action, with a timeout and fallback to bundled.

Price boundary: we only ever *suggest* prices here; the platform's versioned
`price_list` stays the billing source of truth (see services/pricing.py).
"""
from __future__ import annotations

import importlib.metadata
import logging
from decimal import Decimal
from typing import Any

import httpx
import litellm

logger = logging.getLogger(__name__)

# Catalog fields we can sync from litellm (price is handled separately via PriceList).
SYNCABLE_FIELDS = ("context_window", "modality_input", "modality_output", "capabilities")


def current_version() -> str:
    """Installed litellm package version, used as price `source_note` provenance."""
    try:
        return importlib.metadata.version("litellm")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def _per_1k(cost_per_token: Any) -> str | None:
    """litellm prices are per-token; our catalog stores per-1k. Returns a string
    (Decimal-friendly) or None when the source is missing."""
    if cost_per_token is None:
        return None
    try:
        # normalize strips trailing zeros; :f avoids exponent notation (e.g. "0.0025").
        d = (Decimal(str(cost_per_token)) * 1000).normalize()
        return f"{d:f}"
    except (ValueError, ArithmeticError):
        return None


def _modality(entry: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Map litellm `mode` + flags to our (modality_input, modality_output)."""
    mode = entry.get("mode") or "chat"
    if mode == "image_generation":
        return ["text"], ["image"]
    if mode in ("audio_transcription", "audio_speech"):
        return (["audio"], ["text"]) if mode == "audio_transcription" else (["text"], ["audio"])
    # chat / completion / embedding / responses → text; add image input on vision.
    inp = ["text", "image"] if entry.get("supports_vision") else ["text"]
    return inp, ["text"]


def _capabilities(entry: dict[str, Any]) -> list[str]:
    caps: list[str] = []
    mode = entry.get("mode") or "chat"
    if mode in ("chat", "completion", "responses"):
        caps.append("chat")
    if entry.get("supports_function_calling"):
        caps.append("function_calling")
    if entry.get("supports_vision"):
        caps.append("vision")
    if entry.get("supports_reasoning"):
        caps.append("reasoning")
    return caps or ["chat"]


def metadata_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Map a litellm registry entry to our syncable catalog fields."""
    ctx = entry.get("max_input_tokens") or entry.get("max_tokens") or 0
    modality_input, modality_output = _modality(entry)
    return {
        "context_window": int(ctx),
        "modality_input": modality_input,
        "modality_output": modality_output,
        "capabilities": _capabilities(entry),
    }


def price_from_entry(entry: dict[str, Any]) -> dict[str, str | None] | None:
    """Suggested per-1k price from a litellm entry, or None if no input cost."""
    inp = _per_1k(entry.get("input_cost_per_token"))
    if inp is None:
        return None
    return {
        "input_per_1k": inp,
        "output_per_1k": _per_1k(entry.get("output_cost_per_token")) or "0",
        "cached_input_per_1k": _per_1k(entry.get("cache_read_input_token_cost")),
    }


def lookup(key: str, registry: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Syncable metadata for a registry key, or None if litellm has no such model."""
    reg = registry if registry is not None else litellm.model_cost
    entry = reg.get(key)
    if entry is None:
        return None
    return metadata_from_entry(entry)


def suggest_price(key: str, registry: dict[str, Any] | None = None) -> dict[str, str | None] | None:
    reg = registry if registry is not None else litellm.model_cost
    entry = reg.get(key)
    return price_from_entry(entry) if entry is not None else None


def _relevance(key: str, q: str) -> tuple[int, int]:
    """Lower sorts first: exact < final-segment-exact < prefix < contains, then
    by key length (shorter = closer)."""
    kl = key.lower()
    last = kl.split("/", 1)[-1]
    if kl == q or last == q:
        rank = 0
    elif kl.startswith(q) or last.startswith(q):
        rank = 1
    else:
        rank = 2
    return (rank, len(key))


def search(q: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search registry keys by substring, ranked by relevance (for the picker)."""
    q = (q or "").strip().lower()
    matches: list[str] = []
    for key, entry in litellm.model_cost.items():
        if key == "sample_spec" or not isinstance(entry, dict):
            continue
        if q and q not in key.lower():
            continue
        matches.append(key)
    matches.sort(key=lambda k: _relevance(k, q))
    out: list[dict[str, Any]] = []
    for key in matches[:limit]:
        entry = litellm.model_cost[key]
        meta = metadata_from_entry(entry)
        out.append(
            {
                "key": key,
                "provider": entry.get("litellm_provider"),
                "mode": entry.get("mode"),
                "context_window": meta["context_window"],
                "supports_vision": bool(entry.get("supports_vision")),
                "suggested_price": price_from_entry(entry),
            }
        )
    return out


def bundled() -> dict[str, Any]:
    """The pinned, in-memory registry shipped with the installed litellm package."""
    return litellm.model_cost


async def fetch_latest(timeout: float = 5.0) -> dict[str, Any] | None:
    """Live-fetch the latest registry from GitHub (egress: raw.githubusercontent.com
    :443). Returns the map, or None on timeout/error so callers fall back to bundled."""
    url = getattr(litellm, "model_cost_map_url", None)
    if not url:  # pragma: no cover
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
    except Exception as exc:
        logger.warning("litellm registry live fetch failed; falling back to bundled: %s", exc)
        return None
