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


# --- Phase 32 (043): realtime WS URL + smoke (admin "test model" recipe) -----
def test_build_realtime_url_azure_has_intent_and_apiversion():
    from ai_api.proxy.upstream import _AZURE_REALTIME_API_VERSION, _build_realtime_url

    url = _build_realtime_url("https://my-foundry.openai.azure.com", "azure/gpt-realtime-whisper")
    assert url.startswith("wss://my-foundry.openai.azure.com/openai/realtime?")
    assert "intent=transcription" in url            # REQUIRED or Azure → HTTP 400
    # NO deployment= : with it, Azure routes to a conversation session the
    # transcription model can't do (verified live). Model comes via session.update.
    assert "deployment=" not in url
    assert f"api-version={_AZURE_REALTIME_API_VERSION}" in url


def test_build_realtime_url_openai_form():
    from ai_api.proxy.upstream import _build_realtime_url

    url = _build_realtime_url(None, "gpt-realtime-whisper", provider="openai")
    # OpenAI: model goes in session.update, not the URL; just the intent.
    assert url == "wss://api.openai.com/v1/realtime?intent=transcription"


# --- realtime WS smoke (admin "test model" recipe) ---------------------------
class _FakeSmokeWS:
    """A scripted upstream realtime WS for the smoke test (sent frames + recv queue)."""

    def __init__(self, events):
        self.events = list(events)
        self.sent = []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if self.events:
            return self.events.pop(0)
        raise RuntimeError("no more events")

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_realtime_smoke_ok_on_first_server_event():
    import json

    ws = _FakeSmokeWS([json.dumps({"type": "transcription_session.created"})])
    with patch("ai_api.proxy.upstream.open_realtime_ws", new=AsyncMock(return_value=ws)) as opener:
        out = await upstream.realtime_smoke(
            model="azure/gpt-realtime-whisper", api_key="k",
            api_base="https://x", api_version="2024-10-01-preview",
        )
    assert out["ok"] is True and out["first_event"] == "transcription_session.created"
    # provider derived from the slug prefix; smoke just awaits the auto-created
    # session event (Azure emits it on connect — no client send needed).
    assert opener.call_args.kwargs["provider"] == "azure"
    assert ws.sent == []
    assert ws.closed is True  # always closes the upstream WS


@pytest.mark.asyncio
async def test_realtime_smoke_raises_on_error_event():
    import json

    ws = _FakeSmokeWS([json.dumps({"type": "error", "error": {"message": "deployment not found"}})])
    with (
        patch("ai_api.proxy.upstream.open_realtime_ws", new=AsyncMock(return_value=ws)),
        pytest.raises(RuntimeError, match="deployment not found"),
    ):
        await upstream.realtime_smoke(model="azure/gpt-realtime-whisper", api_key="k")
    assert ws.closed is True
