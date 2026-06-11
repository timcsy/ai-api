"""Phase 31 (042) US3: POST /v1/search — per-query, via the registry.
Validates the spec maps the slug onto asearch's `search_provider` arg."""
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

SR = "exa-search"


async def _alloc(c, admin, model=SR):
    r = await c.post("/admin/allocations", headers=admin,
                     json={"subject": "alice@example.com", "resource_model": model})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed_price(per_query):
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(id=str(ULID()), provider="azure", model=SR,
              input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
              price_unit="query", price_per_unit_usd=Decimal(per_query),
              effective_from=datetime.now(UTC) - timedelta(days=1),
              created_at=datetime.now(UTC), created_by="test"))
        await s.commit()


async def _last(o):
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(CallRecord).where(CallRecord.outcome == o)
                .order_by(CallRecord.started_at.desc()))).scalars().all()
        return rows[0] if rows else None


@pytest.mark.asyncio
async def test_search_200_billed_per_query(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _seed_price("0.002")
    stub = {"results": [{"url": "http://x", "title": "t"}]}
    captured = {}
    async def _fake(**kw):
        captured.update(kw)
        return stub
    with patch("ai_api.proxy.upstream.asearch", new=AsyncMock(side_effect=_fake)):
        r = await app_client.post("/v1/search", headers={"Authorization": f"Bearer {alloc['token']}"},
                                  json={"model": SR, "query": "what is rag"})
    assert r.status_code == 200, r.text
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "query" and rec.quantity == 1
    assert rec.cost_usd == Decimal("0.002") and rec.allocation_id == alloc["id"]
    # spec mapped the slug onto search_provider (not model)
    assert "search_provider" in captured and captured["query"] == "what is rag"


@pytest.mark.asyncio
async def test_search_unpriced_zero(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.asearch", new=AsyncMock(return_value={"results": []})):
        r = await app_client.post("/v1/search", headers={"Authorization": f"Bearer {alloc['token']}"},
                                  json={"model": SR, "query": "q"})
    assert r.status_code == 200
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "query" and rec.cost_usd == Decimal(0)


@pytest.mark.asyncio
async def test_search_400_missing_query(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post("/v1/search", headers={"Authorization": f"Bearer {alloc['token']}"},
                              json={"model": SR})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_search_401(app_client: AsyncClient):
    r = await app_client.post("/v1/search", json={"model": SR, "query": "q"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_search_upstream_error(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.asearch", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await app_client.post("/v1/search", headers={"Authorization": f"Bearer {alloc['token']}"},
                                  json={"model": SR, "query": "q"})
    assert r.status_code == 502
    assert (await _last(CallOutcome.upstream_error)) is not None
