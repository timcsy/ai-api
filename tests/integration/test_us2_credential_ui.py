"""Phase 5 T025 / US2: full credential lifecycle from admin perspective.

Scenarios:
1. Admin creates credential → proxy can use it
2. Admin rotates → proxy uses new key, old key gone
3. Admin disables → proxy returns 503
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


def _stub() -> dict:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "created": 0,
        "model": "test",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _alloc(client: AsyncClient, admin_headers: dict, model: str) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us2_full_lifecycle(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # 1) Admin creates Anthropic credential
    create = await app_client.post(
        "/admin/providers",
        headers=admin_headers,
        json={"provider": "anthropic", "label": "primary", "api_key": "sk-ant-original-123"},
    )
    assert create.status_code == 201
    cred_id = create.json()["id"]
    assert create.json()["api_key"] == "sk-ant-original-123"  # one-time plaintext

    # 2) Member can use it via proxy
    alloc = await _alloc(app_client, admin_headers, "anthropic/claude-3-5-sonnet")
    seen_keys: list[str] = []

    async def fake(**kwargs):
        seen_keys.append(kwargs["api_key"])
        return _stub()

    with patch("litellm.acompletion", side_effect=fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "anthropic/claude-3-5-sonnet",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 200
    assert seen_keys[-1] == "sk-ant-original-123"

    # 3) Admin rotates credential
    rot = await app_client.post(
        f"/admin/providers/{cred_id}/rotate",
        headers=admin_headers,
        json={"api_key": "sk-ant-rotated-456"},
    )
    assert rot.status_code == 200
    assert rot.json()["api_key"] == "sk-ant-rotated-456"

    # 4) Proxy now uses new key, never the old one
    with patch("litellm.acompletion", side_effect=fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "anthropic/claude-3-5-sonnet",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 200
    assert seen_keys[-1] == "sk-ant-rotated-456"

    # 5) Admin disables credential
    dis = await app_client.post(
        f"/admin/providers/{cred_id}/disable", headers=admin_headers
    )
    assert dis.status_code == 200
    assert dis.json()["status"] == "disabled"

    # 6) Proxy now returns 503 (no active credential for anthropic)
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={
            "model": "anthropic/claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "provider_unavailable"
