"""Phase 5: thin litellm wrapper. Caller (router) resolves credential & passes params.

Multi-provider routing happens in `router.py` (which has the session); this module
only translates the resolved credential into a litellm.acompletion call.
"""
from __future__ import annotations

from typing import Any

import litellm


async def acompletion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream LLM via litellm.

    `model` must include provider prefix (e.g. `azure/gpt-4o-mini`,
    `anthropic/claude-3-5-sonnet`, `openai/gpt-4o`, `gemini/gemini-1.5-pro`).
    """
    extra: dict[str, Any] = {"api_key": api_key}
    if api_base:
        extra["api_base"] = api_base
    if api_version:
        extra["api_version"] = api_version
    extra.update(kwargs)
    return await litellm.acompletion(model=model, messages=messages, **extra)


async def aresponses(
    *,
    model: str,
    input: Any,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream Responses API via litellm.

    `model` must include a provider prefix (e.g. `azure/gpt-5`, `openai/o4-mini`).
    OpenAI/Azure go native (high fidelity); other providers are bridged by litellm.
    Codex-relevant params (`stream`, `tools`, `reasoning`, `include`, `store`,
    `previous_response_id`, ...) pass through via **kwargs. NULL/empty extras are
    dropped so we don't override litellm defaults.
    """
    extra: dict[str, Any] = {"api_key": api_key}
    if api_base:
        extra["api_base"] = api_base
    if api_version:
        extra["api_version"] = api_version
    extra.update({k: v for k, v in kwargs.items() if v is not None})
    return await litellm.aresponses(model=model, input=input, **extra)


def _extra(api_key: str, api_base: str | None, api_version: str | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, Any] = {"api_key": api_key}
    if api_base:
        extra["api_base"] = api_base
    if api_version:
        extra["api_version"] = api_version
    extra.update({k: v for k, v in kwargs.items() if v is not None})
    return extra


async def aembedding(
    *,
    model: str,
    input: Any,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream embeddings via litellm (Phase 26: admin model test)."""
    return await litellm.aembedding(model=model, input=input, **_extra(api_key, api_base, api_version, kwargs))


async def aspeech(
    *,
    model: str,
    input: str,
    voice: str,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream text-to-speech via litellm (Phase 26: admin model test)."""
    return await litellm.aspeech(
        model=model, input=input, voice=voice, **_extra(api_key, api_base, api_version, kwargs)
    )


async def aimage_generation(
    *,
    model: str,
    prompt: str,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream image generation via litellm (Phase 26: admin model test)."""
    return await litellm.aimage_generation(
        model=model, prompt=prompt, **_extra(api_key, api_base, api_version, kwargs)
    )


async def aocr(
    *,
    model: str,
    document: Any,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream OCR via litellm (Phase 29 ②: /v1/ocr). `document` is a JSON
    dict (URL or base64) — no multipart/binary."""
    return await litellm.aocr(
        model=model, document=document, **_extra(api_key, api_base, api_version, kwargs)
    )


async def arerank(
    *,
    model: str,
    query: str,
    documents: Any,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream rerank via litellm (Phase 29 ③: /v1/rerank). JSON in/out."""
    return await litellm.arerank(
        model=model, query=query, documents=documents,
        **_extra(api_key, api_base, api_version, kwargs),
    )


async def atranscription(
    *,
    model: str,
    file: Any,
    api_key: str,
    api_base: str | None = None,
    api_version: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call upstream speech-to-text via litellm (Phase 29 ③: /v1/audio/transcriptions).
    `file` is a (filename, bytes) tuple from a multipart upload."""
    return await litellm.atranscription(
        model=model, file=file, **_extra(api_key, api_base, api_version, kwargs)
    )
