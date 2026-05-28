"""Phase 11 T036/T037: /v1/responses store + previous_response_id attribution isolation."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog

RESP_MODEL = "azure/gpt-5"


async def _seed_catalog_provider(client: AsyncClient, admin_headers: dict[str, str]) -> None:
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


async def _alloc(client: AsyncClient, admin_headers: dict[str, str], subject: str) -> dict:
    a = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": subject, "resource_model": RESP_MODEL},
    )
    assert a.status_code == 201, a.text
    return a.json()


def _stub(resp_id: str = "resp_store_1") -> dict:
    return {"id": resp_id, "object": "response", "output": [], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}


@pytest.mark.asyncio
async def test_store_then_continue_same_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_catalog_provider(app_client, admin_headers)
    alloc = await _alloc(app_client, admin_headers, "alice@example.com")
    hdr = {"Authorization": f"Bearer {alloc['token']}"}

    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        r1 = await app_client.post(
            "/v1/responses", headers=hdr,
            json={"model": RESP_MODEL, "input": "hi", "store": True},
        )
    assert r1.status_code == 200, r1.text

    # Continue with the stored id — same allocation → allowed, id forwarded upstream.
    mock = AsyncMock(return_value=_stub("resp_store_2"))
    with patch("ai_api.proxy.upstream.aresponses", new=mock):
        r2 = await app_client.post(
            "/v1/responses", headers=hdr,
            json={"model": RESP_MODEL, "input": "again", "previous_response_id": "resp_store_1"},
        )
    assert r2.status_code == 200, r2.text
    assert mock.await_args.kwargs["previous_response_id"] == "resp_store_1"


@pytest.mark.asyncio
async def test_continue_other_allocation_forbidden(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_catalog_provider(app_client, admin_headers)
    a1 = await _alloc(app_client, admin_headers, "alice@example.com")
    a2 = await _alloc(app_client, admin_headers, "bob@example.com")

    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        await app_client.post(
            "/v1/responses", headers={"Authorization": f"Bearer {a1['token']}"},
            json={"model": RESP_MODEL, "input": "hi", "store": True},
        )
    # B tries to continue A's response.
    r = await app_client.post(
        "/v1/responses", headers={"Authorization": f"Bearer {a2['token']}"},
        json={"model": RESP_MODEL, "input": "x", "previous_response_id": "resp_store_1"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "response_forbidden"


@pytest.mark.asyncio
async def test_continue_unknown_not_found(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_catalog_provider(app_client, admin_headers)
    alloc = await _alloc(app_client, admin_headers, "alice@example.com")
    r = await app_client.post(
        "/v1/responses", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": RESP_MODEL, "input": "x", "previous_response_id": "ghost"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "response_not_found"
