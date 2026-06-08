"""Phase 25 US3 (FR-004): admin manual override of responses support — source
"manual", overrides tested; available=false is the only runtime pre-block."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog
from ai_api.services import responses_support as rs

MODEL = "azure/gpt-5"


async def _seed(slug: str, caps: list[str]) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name=slug, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=caps, context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()


async def _provider(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await client.post(
        "/admin/providers", headers=admin_headers,
        json={"provider": "azure", "label": "test", "api_key": "az-test-12345678"},
    )
    assert r.status_code in (200, 201), r.text


async def _alloc(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": MODEL},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_unavailable_overrides_tested_and_blocks_runtime(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # start tested-available
    await _seed(MODEL, ["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    await _provider(app_client, admin_headers)

    r = await app_client.post(
        "/admin/catalog/models/azure/gpt-5/responses-support",
        headers=admin_headers, json={"available": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["support"] == {"state": "unavailable", "source": "manual"}

    # runtime now pre-blocks even though it would otherwise be tried
    alloc = await _alloc(app_client, admin_headers)
    called = AsyncMock(return_value={"id": "x", "object": "response", "output": [], "usage": {}})
    with patch("ai_api.proxy.upstream.aresponses", new=called):
        rr = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": MODEL, "input": "hi"},
        )
    assert rr.status_code == 400
    assert rr.json()["error"]["code"] == "model_responses_disabled"
    called.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_available_sets_source_manual(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed(MODEL, ["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    r = await app_client.post(
        "/admin/catalog/models/azure/gpt-5/responses-support",
        headers=admin_headers, json={"available": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["support"] == {"state": "available", "source": "manual"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_responses_support_404(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/catalog/models/azure/ghost/responses-support",
        headers=admin_headers, json={"available": True},
    )
    assert r.status_code == 404, r.text
