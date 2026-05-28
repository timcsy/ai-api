"""SC-007: provider key must not leak via /v1/responses error/body (Phase 11 US1)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog

RESP_MODEL = "azure/gpt-5"


@pytest.fixture
def azure_key() -> str:
    return get_settings().azure_openai_api_key


async def _seed(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=RESP_MODEL, provider="azure", display_name=RESP_MODEL, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=["responses"], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()
    await client.post(
        "/admin/providers", headers=admin_headers,
        json={"provider": "azure", "label": "t", "api_key": "az-test-12345678"},
    )
    a = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": RESP_MODEL},
    )
    return a.json()


@pytest.mark.asyncio
async def test_responses_upstream_error_redacts_key(
    app_client: AsyncClient, admin_headers: dict[str, str], azure_key: str
) -> None:
    alloc = await _seed(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aresponses") as mock:
        mock.side_effect = RuntimeError(f"upstream failed: api_key={azure_key} endpoint=...")
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RESP_MODEL, "input": "hi"},
        )
    assert r.status_code == 502
    assert azure_key not in r.text
    assert azure_key not in "\n".join(f"{k}: {v}" for k, v in r.headers.items())
