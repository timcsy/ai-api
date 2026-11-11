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


async def _create_catalog_model(client: AsyncClient, admin_headers: dict, slug: str) -> None:
    provider = slug.split("/", 1)[0]
    r = await client.post(
        "/admin/catalog/models",
        headers=admin_headers,
        json={
            "slug": slug,
            "provider": provider,
            "display_name": slug,
            "description": "",
            "context_window": 4096,
            "cost_tier": "low",
        },
    )
    assert r.status_code in (200, 201), r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pinned_model_routes_only_to_its_credential(
    app_client: AsyncClient, admin_headers: dict, make_provider_credential
) -> None:
    """A model pinned to one credential routes THERE every call — NOT round-robin.

    Mirrors the real bug: two `azure` resources host different deployments, so
    round-robin 404s half the time (DeploymentNotFound). Pinning the model to the
    resource that hosts it makes every call deterministic."""
    await make_provider_credential(
        provider="azure", label="resA", api_key="az-A", base_url="https://a.openai.azure.com"
    )
    cred_b = await make_provider_credential(
        provider="azure", label="resB", api_key="az-B", base_url="https://b.openai.azure.com"
    )
    await _create_catalog_model(app_client, admin_headers, "azure/gpt-pinned")

    # Pin the model to resource B.
    rp = await app_client.patch(
        "/admin/catalog/models/azure/gpt-pinned",
        headers=admin_headers,
        json={"provider_credential_id": cred_b.id},
    )
    assert rp.status_code == 200, rp.text
    assert rp.json()["provider_credential_id"] == cred_b.id

    alloc = await _create_alloc(app_client, admin_headers, "azure/gpt-pinned")
    seen: list[str] = []

    async def fake(**kwargs):
        seen.append(kwargs["api_key"])
        return _stub()

    with patch("litellm.acompletion", side_effect=fake):
        for _ in range(3):
            r = await app_client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {alloc['token']}"},
                json={"model": "azure/gpt-pinned", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert r.status_code == 200, r.text
    # Every call used resource B — never A (round-robin would have alternated).
    assert seen == ["az-B", "az-B", "az-B"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pinned_to_disabled_credential_is_503(
    app_client: AsyncClient, admin_headers: dict, make_provider_credential
) -> None:
    """A pin to a credential that is later disabled surfaces 503 (visible misconfig),
    not a silent fall-back to round-robin onto the wrong (still-active) resource.

    Two azure creds exist so the provider still HAS an active credential (else the
    access check short-circuits to model_forbidden before credential resolution)."""
    cred_a = await make_provider_credential(
        provider="azure", label="resA", api_key="az-A", base_url="https://a.openai.azure.com"
    )
    cred_b = await make_provider_credential(
        provider="azure", label="resB", api_key="az-B", base_url="https://b.openai.azure.com"
    )
    await _create_catalog_model(app_client, admin_headers, "azure/gpt-pinned2")
    rp = await app_client.patch(
        "/admin/catalog/models/azure/gpt-pinned2",
        headers=admin_headers,
        json={"provider_credential_id": cred_b.id},
    )
    assert rp.status_code == 200, rp.text

    # Disable ONLY the pinned credential; cred_a stays active.
    rd = await app_client.post(f"/admin/providers/{cred_b.id}/disable", headers=admin_headers)
    assert rd.status_code in (200, 204), rd.text
    assert cred_a.id != cred_b.id

    alloc = await _create_alloc(app_client, admin_headers, "azure/gpt-pinned2")
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "azure/gpt-pinned2", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "provider_unavailable"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pin_rejects_cross_provider_credential(
    app_client: AsyncClient, admin_headers: dict, make_provider_credential
) -> None:
    """Pinning an azure model to an openai credential is a 400 (would never route)."""
    openai_cred = await make_provider_credential(
        provider="openai", label="oai", api_key="sk-oai"
    )
    await _create_catalog_model(app_client, admin_headers, "azure/gpt-pinned3")
    rp = await app_client.patch(
        "/admin/catalog/models/azure/gpt-pinned3",
        headers=admin_headers,
        json={"provider_credential_id": openai_cred.id},
    )
    assert rp.status_code == 400, rp.text
    # Admin HTTPExceptions use FastAPI's {"detail": {"error": ...}} envelope.
    assert rp.json()["detail"]["error"]["code"] == "bad_credential"
