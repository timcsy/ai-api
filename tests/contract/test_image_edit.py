"""Phase 31 (042) US4: POST /v1/images/edits — multipart upload, per-image."""
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

IE = "gpt-image-1-edit"


async def _alloc(c, admin, model=IE):
    r = await c.post("/admin/allocations", headers=admin,
                     json={"subject": "alice@example.com", "resource_model": model})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed_price(per_image):
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(id=str(ULID()), provider="azure", model=IE,
              input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
              price_unit="image", price_per_unit_usd=Decimal(per_image),
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
async def test_image_edit_200_billed_per_image(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    await _seed_price("0.04")
    stub = {"created": 0, "data": [{"b64_json": "aGVsbG8="}]}
    with patch("ai_api.proxy.upstream.aimage_edit", new=AsyncMock(return_value=stub)):
        r = await app_client.post("/v1/images/edits",
                                  headers={"Authorization": f"Bearer {alloc['token']}"},
                                  data={"model": IE, "prompt": "make it red"},
                                  files={"image": ("a.png", b"PNGBYTES", "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["b64_json"] == "aGVsbG8="
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.unit == "image" and rec.quantity == 1
    assert rec.cost_usd == Decimal("0.04") and rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_image_edit_400_missing_image(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post("/v1/images/edits",
                              headers={"Authorization": f"Bearer {alloc['token']}"},
                              data={"model": IE, "prompt": "x"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_image_edit_401(app_client: AsyncClient):
    r = await app_client.post("/v1/images/edits", data={"model": IE},
                              files={"image": ("a.png", b"x", "image/png")})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_image_edit_upstream_error(app_client: AsyncClient, admin_headers):
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aimage_edit", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await app_client.post("/v1/images/edits",
                                  headers={"Authorization": f"Bearer {alloc['token']}"},
                                  data={"model": IE}, files={"image": ("a.png", b"x", "image/png")})
    assert r.status_code == 502
    assert (await _last(CallOutcome.upstream_error)) is not None
