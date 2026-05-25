"""Phase 5 T015 / US1: same allocation token can call models from different providers.

Acceptance Scenarios (spec.md US1):
1. Member calls gpt-4o-mini → uses Azure credential
2. Same member calls claude-3-5-sonnet → uses Anthropic credential
3. Model with no provider credential → 503 provider_unavailable
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


def _stub(model: str = "test", content: str = "pong") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _create_alloc(client: AsyncClient, admin_headers: dict, model: str) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us1_scenario1_azure_call_via_db_credential(
    app_client: AsyncClient, admin_headers: dict, make_provider_credential
) -> None:
    """Scenario 1: gpt-4o-mini call uses Azure credential (DB-stored, not env)."""
    await make_provider_credential(
        provider="azure",
        label="primary",
        api_key="azure-db-key",
        base_url="https://primary.openai.azure.com",
        extra_config={"api_version": "2024-06-01"},
    )
    alloc = await _create_alloc(app_client, admin_headers, "azure/gpt-4o-mini")

    captured: dict = {}

    async def fake(**kwargs):
        captured.update(kwargs)
        return _stub(model="azure/gpt-4o-mini")

    with patch("litellm.acompletion", side_effect=fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "azure/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200, r.text
    # DB credential won, not env (would have been "test-azure-key-DO-NOT-LEAK")
    assert captured["api_key"] == "azure-db-key"
    assert captured["api_base"] == "https://primary.openai.azure.com"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us1_scenario2_anthropic_call_via_db_credential(
    app_client: AsyncClient, admin_headers: dict, make_provider_credential
) -> None:
    """Scenario 2: claude-3-5-sonnet call routes to Anthropic credential."""
    await make_provider_credential(
        provider="anthropic", label="primary", api_key="sk-ant-test"
    )
    alloc = await _create_alloc(
        app_client, admin_headers, "anthropic/claude-3-5-sonnet"
    )

    captured: dict = {}

    async def fake(**kwargs):
        captured.update(kwargs)
        return _stub(model="anthropic/claude-3-5-sonnet")

    with patch("litellm.acompletion", side_effect=fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "anthropic/claude-3-5-sonnet",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 200, r.text
    assert captured["api_key"] == "sk-ant-test"
    assert captured["model"] == "anthropic/claude-3-5-sonnet"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us1_scenario3_provider_unavailable_when_no_credential(
    app_client: AsyncClient, admin_headers: dict
) -> None:
    """Scenario 3: anthropic model with no DB credential AND no env fallback → 503."""
    alloc = await _create_alloc(
        app_client, admin_headers, "anthropic/claude-3-5-sonnet"
    )
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={
            "model": "anthropic/claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "provider_unavailable"
    assert "anthropic" in body["error"]["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us1_round_robin_alternates_credentials(
    app_client: AsyncClient, admin_headers: dict, make_provider_credential
) -> None:
    """Two active credentials → consecutive calls use different ones (round-robin)."""
    c1 = await make_provider_credential(
        provider="openai", label="key1", api_key="sk-openai-1"
    )
    c2 = await make_provider_credential(
        provider="openai", label="key2", api_key="sk-openai-2"
    )
    alloc = await _create_alloc(app_client, admin_headers, "openai/gpt-4o")

    seen_keys: list[str] = []

    async def fake(**kwargs):
        seen_keys.append(kwargs["api_key"])
        return _stub()

    with patch("litellm.acompletion", side_effect=fake):
        for _ in range(2):
            r = await app_client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {alloc['token']}"},
                json={"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert r.status_code == 200
    # Two distinct credentials seen across two calls (round-robin by last_used_at)
    assert set(seen_keys) == {"sk-openai-1", "sk-openai-2"}
    assert c1.id != c2.id
