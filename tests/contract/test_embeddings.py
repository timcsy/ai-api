"""Phase 29 (038): contract tests for POST /v1/embeddings.

Mirrors /chat/completions: same preflight (auth / allocation / access / credential),
token billing reused (input tokens), result IS the embedding response. Phase 29
增量①: zero migration, embedding billed as input tokens.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord

EMB = "text-embedding-3-small"  # azure provider via env fallback (like proxy_chat tests)


async def _alloc(client: AsyncClient, admin_headers: dict[str, str], model: str = EMB) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub_embedding() -> dict:
    return {
        "object": "list",
        "model": EMB,
        "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }


async def _last_success_record() -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


@pytest.mark.asyncio
async def test_embeddings_200_and_billed(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aembedding", new=AsyncMock(return_value=_stub_embedding())):
        r = await app_client.post(
            "/v1/embeddings",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": EMB, "input": "hello"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    # billed: one success CallRecord with input tokens, attributed to the allocation
    rec = await _last_success_record()
    assert rec is not None and rec.prompt_tokens == 5 and rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_embeddings_401_no_token(app_client: AsyncClient) -> None:
    r = await app_client.post("/v1/embeddings", json={"model": EMB, "input": "hi"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_embeddings_401_bad_token(app_client: AsyncClient) -> None:
    r = await app_client.post(
        "/v1/embeddings", headers={"Authorization": "Bearer aiapi_nope"},
        json={"model": EMB, "input": "hi"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_embeddings_400_missing_input(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/embeddings", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": EMB},  # no input
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_embeddings_model_mismatch(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # token scoped to EMB but request a different model → model_mismatch
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/embeddings", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "text-embedding-3-large", "input": "hi"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "model_mismatch"


@pytest.mark.asyncio
async def test_embeddings_upstream_error_no_5xx_leak(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aembedding", new=AsyncMock(side_effect=RuntimeError("DeploymentNotFound"))):
        r = await app_client.post(
            "/v1/embeddings", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": EMB, "input": "hi"},
        )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "upstream_error"
    assert "DeploymentNotFound" in r.json()["error"]["message"]
    # recorded as a diagnosable upstream_error
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.upstream_error)
        )).scalars().all()
        assert rows
