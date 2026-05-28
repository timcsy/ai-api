"""Phase 11 T010: upstream.aresponses passes Codex-relevant params through litellm."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_api.proxy import upstream


@pytest.mark.asyncio
async def test_aresponses_forwards_params() -> None:
    with patch("ai_api.proxy.upstream.litellm.aresponses", new=AsyncMock()) as mock:
        await upstream.aresponses(
            model="azure/gpt-5",
            input="hello",
            api_key="sk-secret",
            api_base="https://x",
            api_version="2025-04-01",
            stream=True,
            tools=[{"type": "function"}],
            reasoning={"effort": "high"},
            include=["reasoning.encrypted_content"],
            store=False,
            previous_response_id=None,  # dropped because None
        )
    kwargs = mock.await_args.kwargs
    assert kwargs["model"] == "azure/gpt-5"
    assert kwargs["input"] == "hello"
    assert kwargs["api_key"] == "sk-secret"
    assert kwargs["api_base"] == "https://x"
    assert kwargs["api_version"] == "2025-04-01"
    assert kwargs["stream"] is True
    assert kwargs["tools"] == [{"type": "function"}]
    assert kwargs["reasoning"] == {"effort": "high"}
    assert kwargs["include"] == ["reasoning.encrypted_content"]
    assert kwargs["store"] is False
    assert "previous_response_id" not in kwargs  # None dropped
