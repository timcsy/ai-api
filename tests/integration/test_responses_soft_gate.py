"""Phase 25 US1 (FR-001/002): runtime soft gate for /v1/responses.

No static-flag pre-block: an un-marked but bridgeable model is tried (not pre-400'd);
an unsupported one returns the real upstream error; the ONLY pre-block is admin's
manual "unavailable" (responses:blocked).
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog
from ai_api.services import responses_support as rs

MODEL = "azure/gpt-5"


async def _seed_catalog(slug: str, capabilities: list[str]) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name=slug, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=capabilities, context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()


async def _seed_provider(client: AsyncClient, admin_headers: dict[str, str]) -> None:
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


def _stub() -> dict:
    return {
        "id": "resp_test", "object": "response",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "hi"}]}],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unmarked_model_is_tried_not_preblocked(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # state=unknown (no responses marker) — must NOT be pre-blocked.
    await _seed_catalog(MODEL, ["chat"])
    await _seed_provider(app_client, admin_headers)
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": MODEL, "input": "hi"},
        )
    assert r.status_code == 200, r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unsupported_model_returns_upstream_error(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_catalog(MODEL, ["chat"])
    await _seed_provider(app_client, admin_headers)
    alloc = await _alloc(app_client, admin_headers)
    with patch(
        "ai_api.proxy.upstream.aresponses",
        new=AsyncMock(side_effect=RuntimeError("model does not support responses")),
    ):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": MODEL, "input": "hi"},
        )
    # real upstream cause surfaced (502 upstream_error), not an info-less 400.
    assert r.status_code == 502, r.text
    assert r.json()["error"]["code"] == "upstream_error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_blocked_is_preblocked(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_catalog(MODEL, ["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    await _seed_provider(app_client, admin_headers)
    alloc = await _alloc(app_client, admin_headers)
    # upstream must NOT even be called — pre-blocked.
    called = AsyncMock(return_value=_stub())
    with patch("ai_api.proxy.upstream.aresponses", new=called):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": MODEL, "input": "hi"},
        )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "model_responses_disabled"
    called.assert_not_called()
