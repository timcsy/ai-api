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

    # Patch litellm.acompletion (the lower-level lib) to verify the wrapper
    # injects api_key + api_base from settings, not from the request.
    async def fake(**kwargs):
        fake.kwargs = kwargs  # type: ignore[attr-defined]
        return stub

    with patch("litellm.acompletion", side_effect=fake):
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

    # Verify wrapper injected internally-managed credentials.
    assert fake.kwargs["api_key"]  # type: ignore[attr-defined]
    assert fake.kwargs["api_base"]  # type: ignore[attr-defined]
    assert fake.kwargs["model"] == "azure/gpt-4o-mini"  # type: ignore[attr-defined]
