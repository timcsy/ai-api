"""Contract + basic tests for POST /v1/responses (Phase 11 US1)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord, ModelCatalog

RESP_MODEL = "azure/gpt-5"


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


async def _seed_azure_provider(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await client.post(
        "/admin/providers", headers=admin_headers,
        json={"provider": "azure", "label": "test", "api_key": "az-test-12345678"},
    )
    assert r.status_code in (200, 201), r.text


async def _make_allocation(
    client: AsyncClient, admin_headers: dict[str, str], model: str = RESP_MODEL
) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub_response() -> dict:
    return {
        "id": "resp_test",
        "object": "response",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "hi"}]}],
        "usage": {
            "input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
            "output_tokens_details": {"reasoning_tokens": 5},
            "input_tokens_details": {"cached_tokens": 4},
        },
    }


@pytest.mark.asyncio
async def test_responses_200_non_stream(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_catalog(RESP_MODEL, ["responses"])
    await _seed_azure_provider(app_client, admin_headers)
    alloc = await _make_allocation(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub_response())):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RESP_MODEL, "input": "hi"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["output"][0]["content"][0]["text"] == "hi"

    # Usage recorded with token breakdown.
    sm = get_sessionmaker()
    async with sm() as s:
        rec = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
        )).scalar_one()
    assert rec.prompt_tokens == 10
    assert rec.completion_tokens == 20
    assert rec.reasoning_tokens == 5
    assert rec.cached_tokens == 4


@pytest.mark.asyncio
async def test_responses_401_no_token(app_client: AsyncClient) -> None:
    r = await app_client.post("/v1/responses", json={"model": RESP_MODEL, "input": "x"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_responses_400_missing_input(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_catalog(RESP_MODEL, ["responses"])
    alloc = await _make_allocation(app_client, admin_headers)
    r = await app_client.post(
        "/v1/responses",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": RESP_MODEL},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_responses_manual_blocked_rejected(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # Phase 25: an un-marked model is no longer pre-blocked — the ONLY pre-block is
    # admin's manual "unavailable" (responses:blocked).
    await _seed_catalog(RESP_MODEL, ["tools", "responses:blocked", "responses:manual"])
    await _seed_azure_provider(app_client, admin_headers)
    alloc = await _make_allocation(app_client, admin_headers)
    r = await app_client.post(
        "/v1/responses",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": RESP_MODEL, "input": "hi"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "model_responses_disabled"


@pytest.mark.asyncio
async def test_responses_revoked_rejected(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_catalog(RESP_MODEL, ["responses"])
    alloc = await _make_allocation(app_client, admin_headers)
    rv = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    assert rv.status_code in (200, 204), rv.text
    r = await app_client.post(
        "/v1/responses",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": RESP_MODEL, "input": "hi"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "allocation_revoked"
    # Rejection still attributed to the allocation.
    sm = get_sessionmaker()
    async with sm() as s:
        rec = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.rejected_revoked)
        )).scalar_one()
    assert rec.allocation_id == alloc["id"]
