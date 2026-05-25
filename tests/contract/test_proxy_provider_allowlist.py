"""Contract tests for provider allowlist on /v1/chat/completions."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


async def _make_allocation(
    client: AsyncClient, admin_headers: dict[str, str], resource_model: str = "gpt-4o-mini"
) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": resource_model},
    )
    assert r.status_code == 201
    return r.json()


def _stub() -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.asyncio
async def test_allowed_provider_passes(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers, resource_model="azure/gpt-4o-mini")
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "azure/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_disallowed_provider_rejected_403(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(
        app_client, admin_headers, resource_model="bogusprov/some-model"
    )
    # Phase 5 expanded default allowed_providers to {azure, openai, anthropic, gemini};
    # use an obviously non-existent provider id to exercise the deny path.
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={
            "model": "bogusprov/some-model",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "provider_not_allowed"


@pytest.mark.asyncio
async def test_no_provider_prefix_uses_default(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Model without a `/` should be treated as default provider (`azure`)."""
    alloc = await _make_allocation(app_client, admin_headers, resource_model="gpt-4o-mini")
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_empty_allowlist_fails_app_creation(monkeypatch) -> None:
    """FR-003: service must refuse to start with empty allowed_providers."""
    monkeypatch.setenv("ALLOWED_PROVIDERS", "[]")
    from ai_api.config import get_settings
    from ai_api.main import create_app

    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="ALLOWED_PROVIDERS is empty"):
        create_app()
    get_settings.cache_clear()
