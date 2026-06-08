"""Phase 25 US2 (FR-003): admin "test responses" — a minimal real aresponses call;
the result IS the response (never 5xx for upstream errors). Passing records the
model as responses-available, source "tested"."""
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


def _stub() -> dict:
    return {"id": "resp", "object": "response", "output": [], "usage": {}}


async def _support(slug: str) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        m = await s.get(ModelCatalog, slug)
        return rs.get_support(m.capabilities)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_test_responses_pass_marks_tested(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed(MODEL, ["chat"])
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-5/test-responses", headers=admin_headers
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "latency_ms" in body
    assert body["support"] == {"state": "available", "source": "tested"}
    assert await _support(MODEL) == {"state": "available", "source": "tested"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_test_responses_fail_keeps_unknown_and_no_5xx(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed(MODEL, ["chat"])
    await _provider(app_client, admin_headers)
    with patch(
        "ai_api.proxy.upstream.aresponses",
        new=AsyncMock(side_effect=RuntimeError("not supported")),
    ):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-5/test-responses", headers=admin_headers
        )
    assert r.status_code == 200, r.text  # result IS the response, never 5xx
    body = r.json()
    assert body["ok"] is False
    assert body["error_type"] and body["message"]
    assert await _support(MODEL) == {"state": "unknown", "source": None}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_test_responses_404_for_unknown_slug(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/catalog/models/azure/ghost/test-responses", headers=admin_headers
    )
    assert r.status_code == 404, r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_test_responses_does_not_flip_manual_block(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # manual "unavailable" wins: a passing test must NOT flip it back to available.
    await _seed(MODEL, ["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-5/test-responses", headers=admin_headers
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert await _support(MODEL) == {"state": "unavailable", "source": "manual"}
