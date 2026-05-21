"""Thin wrapper around litellm.acompletion for the Azure OpenAI upstream.

Using litellm as a library (not the Proxy Server form) — keeps multi-provider
abstraction and cost tracking while giving us full control over auth/guard
middlewares per research.md §1-§2.
"""
from __future__ import annotations

from typing import Any

import litellm

from ai_api.config import get_settings


async def acompletion(*, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """Call Azure OpenAI through litellm with internally-managed credentials."""
    settings = get_settings()
    azure_model = model if model.startswith("azure/") else f"azure/{model}"
    return await litellm.acompletion(
        model=azure_model,
        messages=messages,
        api_key=settings.azure_openai_api_key,
        api_base=settings.azure_openai_api_base,
        api_version=settings.azure_openai_api_version,
        **kwargs,
    )
