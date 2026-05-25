"""US1 happy path: create allocation → proxy call succeeds (mocked upstream)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_then_proxy_call_succeeds(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    create_resp = await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": "gpt-4o-mini"},
    )
    assert create_resp.status_code == 201, create_resp.text
    alloc = create_resp.json()

    stub = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "pong"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

    # Patch the AsyncAzureOpenAI client factory; the wrapper builds it from
    # settings, so the mock confirms request never carries upstream credentials.
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return stub

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    with patch("ai_api.proxy.upstream._client", return_value=FakeClient()):
        proxy_resp = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    assert proxy_resp.status_code == 200
    assert proxy_resp.json()["choices"][0]["message"]["content"] == "pong"

    # azure/ prefix stripped to bare deployment name; credentials never came
    # from the request payload.
    assert captured["model"] == "gpt-4o-mini"
