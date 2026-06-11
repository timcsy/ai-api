"""Phase 31 follow-up: data-driven 'test model' recipes — the single source of
truth for *how* (and whether) each model kind can be auto-tested.

Root-fixes the drift that produced false passes (0ms): the admin test button used
an if/elif over {chat,embedding,tts,image} while `is_supported` separately said
"anything except stt/unknown". When ocr/rerank/… kinds were added, is_supported
said "supported" but no branch ran → the call silently did nothing → "通過 0ms".

Now a kind is auto-testable IFF it has a recipe here. Adding a kind without a
recipe → honestly "尚不支援自動測試", never a fake pass. `is_testable` /
`is_billable` both DERIVE from this table, so they cannot drift from it again.

`call` takes the `common` dict ({model, api_key, api_base, api_version}) and makes
the minimal real upstream call. Use `upstream.X` attribute access (not a direct
import) so test mocks on `ai_api.proxy.upstream.*` are honoured.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ai_api.proxy import upstream


@dataclass(frozen=True)
class TestRecipe:
    call: Callable[[dict[str, Any]], Awaitable[Any]]
    billable: bool = False  # kinds whose minimal test still costs real money


# kind → how to test it. NO entry ⇒ not auto-testable (honest "unsupported").
# Omitted on purpose: ocr / image_edit (need a sample document/image to send),
# search (routed by search_provider, not model), stt (needs an audio file),
# unknown. They show "尚不支援自動測試" instead of a fake pass.
RECIPES: dict[str, TestRecipe] = {
    "chat": TestRecipe(
        # Generous max_tokens: reasoning models spend the budget on reasoning, so a
        # tiny cap → "raise max_tokens" even when reachable; normal models stop fast.
        lambda c: upstream.acompletion(
            messages=[{"role": "user", "content": "ping"}], max_tokens=2048, **c
        )
    ),
    "embedding": TestRecipe(lambda c: upstream.aembedding(input="ping", **c)),
    "tts": TestRecipe(lambda c: upstream.aspeech(input="hi", voice="alloy", **c), billable=True),
    # Don't pin a size: newer image models reject tiny sizes; the default is valid.
    "image": TestRecipe(lambda c: upstream.aimage_generation(prompt="a red dot", n=1, **c), billable=True),
    "moderation": TestRecipe(lambda c: upstream.amoderation(input="ping", **c)),
    "rerank": TestRecipe(lambda c: upstream.arerank(query="ping", documents=["a", "b"], **c)),
}


def is_testable(kind: str) -> bool:
    """A kind can be auto-tested IFF a recipe exists — never drifts from RECIPES."""
    return kind in RECIPES


def is_billable(kind: str) -> bool:
    """Whether the auto-test costs real money (derived from the recipe)."""
    recipe = RECIPES.get(kind)
    return bool(recipe and recipe.billable)
