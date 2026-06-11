"""Phase 29 ③ (041) US2: contract tests for POST /v1/rerank.

rerank is billed per QUERY (a non-token unit, second after OCR's page) via the
generalized billing layer. Upstream litellm.arerank is mocked.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord, PriceList

RR = "cohere-rerank-v3.5"  # azure provider via env fallback


async def _alloc(client: AsyncClient, admin_headers: dict[str, str], model: str = RR) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub_rerank() -> dict:
    return {"id": "r1", "results": [{"index": 1, "relevance_score": 0.9}], "meta": {}}


async def _seed_query_price(per_query: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider="azure", model=RR,
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="query", price_per_unit_usd=Decimal(per_query),
            effective_from=datetime.now(UTC) - timedelta(days=1),
            created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()


async def _last(outcome: CallOutcome) -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == outcome)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


@pytest.mark.asyncio
async def test_rerank_200_billed_per_query(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    await _seed_query_price("0.002")
    with patch("ai_api.proxy.upstream.arerank", new=AsyncMock(return_value=_stub_rerank())):
        r = await app_client.post(
            "/v1/rerank", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RR, "query": "q", "documents": ["a", "b"]},
        )
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["index"] == 1
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "query" and rec.quantity == 1
    assert rec.cost_usd == Decimal("0.002")
    assert rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_rerank_unpriced_cost_zero(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.arerank", new=AsyncMock(return_value=_stub_rerank())):
        r = await app_client.post(
            "/v1/rerank", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RR, "query": "q", "documents": ["a"]},
        )
    assert r.status_code == 200
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "query" and rec.cost_usd == Decimal(0)


@pytest.mark.asyncio
async def test_rerank_400_missing_query(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/rerank", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": RR, "documents": ["a"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_rerank_401(app_client: AsyncClient) -> None:
    r = await app_client.post("/v1/rerank", json={"model": RR, "query": "q", "documents": ["a"]})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_rerank_upstream_error(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.arerank",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await app_client.post(
            "/v1/rerank", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RR, "query": "q", "documents": ["a"]},
        )
    assert r.status_code == 502
    rec = await _last(CallOutcome.upstream_error)
    assert rec is not None and rec.allocation_id == alloc["id"]
