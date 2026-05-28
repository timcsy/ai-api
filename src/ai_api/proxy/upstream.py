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
