"""Phase 31 (042) US2: POST /v1/moderations — token-billed, via the registry."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord

MOD = "text-moderation-latest"


async def _alloc(c, admin, model=MOD):
    r = await c.post("/admin/allocations", headers=admin,
                     json={"subject": "alice@example.com", "resource_model": model})
    assert r.status_code == 201, r.text
    return r.json()


async def _last(o):
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(CallRecord).where(CallRecord.outcome == o)
                .order_by(CallRecord.started_at.desc()))).scalars().all()
        return rows[0] if rows else None


@pytest.mark.asyncio
async def test_moderation_200_billed(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    stub = {"id": "m", "results": [{"flagged": False}], "usage": {"prompt_tokens": 6, "total_tokens": 6}}
    with patch("ai_api.proxy.upstream.amoderation", new=AsyncMock(return_value=stub)):
        r = await app_client.post("/v1/moderations", headers={"Authorization": f"Bearer {alloc['token']}"},
                                  json={"model": MOD, "input": "some text"})
    assert r.status_code == 200, r.text
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.prompt_tokens == 6 and rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_moderation_400_missing_input(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post("/v1/moderations", headers={"Authorization": f"Bearer {alloc['token']}"},
                              json={"model": MOD})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_moderation_401(app_client: AsyncClient):
    r = await app_client.post("/v1/moderations", json={"model": MOD, "input": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_moderation_upstream_error(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.amoderation", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await app_client.post("/v1/moderations", headers={"Authorization": f"Bearer {alloc['token']}"},
                                  json={"model": MOD, "input": "x"})
    assert r.status_code == 502
    assert (await _last(CallOutcome.upstream_error)) is not None
