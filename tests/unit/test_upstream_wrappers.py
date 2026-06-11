"""Phase 26: upstream wrappers for embedding / speech / image — mirror acompletion's
credential injection (api_key always; drop None api_base/api_version)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_api.proxy import upstream


@pytest.mark.asyncio
async def test_aembedding_injects_key_and_drops_none():
    with patch("litellm.aembedding", new=AsyncMock(return_value="ok")) as m:
        await upstream.aembedding(model="azure/text-embedding-3", input="ping", api_key="k")
    kw = m.call_args.kwargs
    assert kw["model"] == "azure/text-embedding-3" and kw["input"] == "ping" and kw["api_key"] == "k"
    assert "api_base" not in kw and "api_version" not in kw


@pytest.mark.asyncio
async def test_aspeech_passes_voice_and_base():
    with patch("litellm.aspeech", new=AsyncMock(return_value="ok")) as m:
        await upstream.aspeech(
            model="openai/tts-1", input="hi", voice="alloy", api_key="k", api_base="https://x"
        )
    kw = m.call_args.kwargs
    assert kw["voice"] == "alloy" and kw["api_base"] == "https://x" and kw["api_key"] == "k"


@pytest.mark.asyncio
async def test_aimage_generation_passes_prompt_and_version():
    with patch("litellm.aimage_generation", new=AsyncMock(return_value="ok")) as m:
        await upstream.aimage_generation(
            model="azure/dall-e-3", prompt="a red dot", api_key="k", api_version="2024-02-01", size="256x256"
        )
    kw = m.call_args.kwargs
    assert kw["prompt"] == "a red dot" and kw["api_version"] == "2024-02-01" and kw["size"] == "256x256"


@pytest.mark.asyncio
async def test_aocr_remaps_azure_to_azure_ai():
    # litellm OCR supports azure_ai/ (Azure AI Foundry) but NOT azure/ (Azure
    # OpenAI). Mistral Document AI lives on Foundry — same endpoint/key, reached
    # via the azure_ai/ prefix — so aocr must remap azure/ → azure_ai/.
    with patch("litellm.aocr", new=AsyncMock(return_value="ok")) as m:
        await upstream.aocr(
            model="azure/mistral-document-ai-2512", document={"x": 1},
            api_key="k", api_base="https://x", api_version="2024-02-01",
        )
    kw = m.call_args.kwargs
    assert kw["model"] == "azure_ai/mistral-document-ai-2512"
    assert kw["api_base"] == "https://x" and kw["api_key"] == "k"


@pytest.mark.asyncio
async def test_aocr_leaves_non_azure_provider_untouched():
    with patch("litellm.aocr", new=AsyncMock(return_value="ok")) as m:
        await upstream.aocr(model="mistral/mistral-ocr-latest", document={"x": 1}, api_key="k")
    assert m.call_args.kwargs["model"] == "mistral/mistral-ocr-latest"
