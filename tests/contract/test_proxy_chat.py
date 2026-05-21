"""Contract tests for POST /v1/chat/completions."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


async def _make_allocation(
    client: AsyncClient, admin_headers: dict[str, str], model: str = "gpt-4o-mini"
) -> dict:
    response = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _stub_litellm_response() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.asyncio
async def test_proxy_chat_200(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub_litellm_response()
        response = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "hello"


@pytest.mark.asyncio
async def test_proxy_chat_401_no_token(app_client: AsyncClient) -> None:
    response = await app_client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": []},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_proxy_chat_401_bad_token(app_client: AsyncClient) -> None:
    response = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer aiapi_nope"},
        json={"model": "gpt-4o-mini", "messages": []},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_proxy_chat_403_model_mismatch(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers, model="gpt-4o-mini")
    response = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={
            "model": "gpt-4-different",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "model_mismatch"
