"""Phase 23 US1: admin LiteLLM picker endpoints (search + suggest)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_finds_registry_key(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/catalog/litellm/search?q=gpt-4o&limit=10", headers=admin_headers)
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    hit = next((x for x in results if x["key"] == "azure/gpt-4o"), None)
    assert hit is not None
    assert hit["context_window"] == 128000
    assert hit["suggested_price"]["input_per_1k"] == "0.0025"


@pytest.mark.asyncio
async def test_search_respects_limit(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/catalog/litellm/search?q=gpt&limit=3", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 3


@pytest.mark.asyncio
async def test_suggest_returns_metadata_and_price(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/catalog/litellm/suggest/azure/gpt-4o", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug_default"] == "azure/gpt-4o"
    assert body["metadata"]["context_window"] == 128000
    assert body["suggested_price"]["input_per_1k"] == "0.0025"
    assert body["imported_version"]


@pytest.mark.asyncio
async def test_suggest_unknown_key_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/catalog/litellm/suggest/azure/not-real-xyz", headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "litellm_model_not_found"
