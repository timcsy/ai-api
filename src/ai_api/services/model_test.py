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

import base64
import io
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ai_api.proxy import upstream

# --- Minimal fixtures for binary / document test recipes ---------------------
# These are *format*-valid: a real 1x1 PNG and a real silent WAV, so a passing
# test means upstream accepted a well-formed request. Whether a SPECIFIC model
# accepts this minimal input can only be confirmed against a live provider —
# local tests mock `upstream.*`, so they verify dispatch, not provider behaviour.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)


def _silent_wav(seconds: float = 0.3, rate: int = 16000) -> bytes:
    """A short silent mono 16-bit WAV. Length matters: Azure whisper rejects
    clips under 0.1s ("audio_too_short"), so default to 0.3s with margin."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


_WAV_SILENCE = _silent_wav()
# OCR document: a base64 image data-URL (Mistral document-ai accepts image_url docs).
_OCR_DOCUMENT = {
    "type": "image_url",
    "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==",
}


@dataclass(frozen=True)
class TestRecipe:
    call: Callable[[dict[str, Any]], Awaitable[Any]]
    billable: bool = False  # kinds whose minimal test still costs real money


# kind → how to test it. NO entry ⇒ not auto-testable (honest "unsupported").
# Only `unknown` is omitted now (a mode we can't map to any real call); every
# inference kind below makes a minimal real upstream call.
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
    # --- binary / document kinds: billable, send a minimal valid fixture ---
    "ocr": TestRecipe(lambda c: upstream.aocr(document=_OCR_DOCUMENT, **c), billable=True),
    "stt": TestRecipe(
        lambda c: upstream.atranscription(file=("ping.wav", _WAV_SILENCE), **c), billable=True
    ),
    "image_edit": TestRecipe(
        lambda c: upstream.aimage_edit(
            image=("ping.png", _PNG_1X1), prompt="make the background white", **c
        ),
        billable=True,
    ),
    # search routes by `search_provider` (not `model`) — remap the common dict
    # explicitly since the wrapper has no `model` parameter to **c into.
    "search": TestRecipe(
        lambda c: upstream.asearch(
            search_provider=c["model"], query="ping",
            api_key=c["api_key"], api_base=c["api_base"], api_version=c["api_version"],
        ),
        billable=True,
    ),
    # realtime is a bidirectional WS, not a one-shot call — the recipe is a minimal
    # WS smoke (handshake + tiny silent append + await first server event). Passing
    # proves egress/key/deployment/protocol; it IS the T027 reachability check from
    # the UI. Billable (a couple seconds of audio).
    "realtime": TestRecipe(lambda c: upstream.realtime_smoke(**c), billable=True),
}


def is_testable(kind: str) -> bool:
    """A kind can be auto-tested IFF a recipe exists — never drifts from RECIPES."""
    return kind in RECIPES


def is_billable(kind: str) -> bool:
    """Whether the auto-test costs real money (derived from the recipe)."""
    recipe = RECIPES.get(kind)
    return bool(recipe and recipe.billable)
