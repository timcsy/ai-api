"""Thin wrapper around the OpenAI SDK (Azure mode) for the upstream call.

Uses the official `openai` Python SDK in AsyncAzureOpenAI mode. Auth and
quota are enforced upstream of this call (proxy.router); this module owns
only the actual HTTP round-trip to Azure OpenAI.
"""
from __future__ import annotations

from typing import Any

from openai import AsyncAzureOpenAI

from ai_api.config import get_settings


def _client() -> AsyncAzureOpenAI:
    settings = get_settings()
    return AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_api_base,
        api_version=settings.azure_openai_api_version,
    )


async def acompletion(*, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """Call Azure OpenAI chat completions with internally-managed credentials.

    `model` is the Azure deployment name; the `azure/` prefix (legacy litellm
    convention) is stripped if present so callers can keep passing either form.
    """
    deployment = model.removeprefix("azure/")
    return await _client().chat.completions.create(
        model=deployment,
        messages=messages,  # type: ignore[arg-type]
        **kwargs,
    )
