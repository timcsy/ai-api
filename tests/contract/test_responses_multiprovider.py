"""Phase 11 T032/T033: /v1/responses across providers (bridge) + capability gate."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _seed(client: AsyncClient, admin_headers: dict[str, str], slug: str, provider: str, caps: list[str]) -> dict:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=provider, display_name=slug, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=caps, context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()
    await client.post(
        "/admin/providers", headers=admin_headers,
        json={"provider": provider, "label": "t", "api_key": "key-test-12345678"},
    )
    a = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": slug},
    )
    assert a.status_code == 201, a.text
    return a.json()


def _stub() -> dict:
    return {"id": "r", "object": "response", "output": [], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}


@pytest.mark.asyncio
async def test_non_openai_provider_bridged(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    slug = "anthropic/claude-sonnet-4"
    alloc = await _seed(app_client, admin_headers, slug, "anthropic", ["responses"])
    mock = AsyncMock(return_value=_stub())
    with patch("ai_api.proxy.upstream.aresponses", new=mock):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": slug, "input": "hi"},
        )
    assert r.status_code == 200, r.text
    # Upstream called with the provider-prefixed model (litellm routes/bridges).
    assert mock.await_args.kwargs["model"] == slug


@pytest.mark.asyncio
async def test_manual_blocked_rejected_cross_provider(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Phase 25: only a manual "unavailable" (responses:blocked) pre-blocks.
    slug = "gemini/gemini-2.5-pro"
    alloc = await _seed(
        app_client, admin_headers, slug, "gemini",
        ["chat", "responses:blocked", "responses:manual"],
    )
    r = await app_client.post(
        "/v1/responses",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": slug, "input": "hi"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "model_responses_disabled"
