"""Phase 29 ② (040): contract tests for POST /v1/ocr.

Mirrors /v1/embeddings preflight; bills per PAGE (non-token unit) via the
generalized billing layer. Upstream litellm.aocr is mocked.
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

OCR = "mistral-document-ai"  # azure provider via env fallback (like embeddings tests)
DOC = {"type": "document_url", "document_url": "https://example.com/f.pdf"}


async def _alloc(client: AsyncClient, admin_headers: dict[str, str], model: str = OCR) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub_ocr(pages: int = 3) -> dict:
    return {
        "model": OCR,
        "pages": [{"index": i, "markdown": f"page {i}"} for i in range(pages)],
        "usage_info": None,
        "object": "ocr.response",
    }


async def _seed_page_price(provider: str, model: str, per_page: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider=provider, model=model,
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="page", price_per_unit_usd=Decimal(per_page),
            effective_from=datetime.now(UTC) - timedelta(days=1),
            created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()


async def _last_record(outcome: CallOutcome) -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == outcome)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


@pytest.mark.asyncio
async def test_ocr_200_billed_per_page(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    await _seed_page_price("azure", OCR, "0.003")
    with patch("ai_api.proxy.upstream.aocr", new=AsyncMock(return_value=_stub_ocr(3))):
        r = await app_client.post(
            "/v1/ocr", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": OCR, "document": DOC},
        )
    assert r.status_code == 200, r.text
    assert len(r.json()["pages"]) == 3
    rec = await _last_record(CallOutcome.success)
    assert rec is not None
    assert rec.unit == "page" and rec.quantity == 3
    assert rec.cost_usd == Decimal("0.009")  # 3 × 0.003
    assert rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_ocr_unpriced_cost_zero(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    # no page price seeded
    with patch("ai_api.proxy.upstream.aocr", new=AsyncMock(return_value=_stub_ocr(2))):
        r = await app_client.post(
            "/v1/ocr", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": OCR, "document": DOC},
        )
    assert r.status_code == 200
    rec = await _last_record(CallOutcome.success)
    assert rec is not None and rec.unit == "page" and rec.quantity == 2
    assert rec.cost_usd == Decimal(0)


@pytest.mark.asyncio
async def test_ocr_401_no_token(app_client: AsyncClient) -> None:
    r = await app_client.post("/v1/ocr", json={"model": OCR, "document": DOC})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ocr_400_missing_document(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/ocr", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": OCR},  # no document
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_ocr_model_mismatch(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/ocr", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "some-other-model", "document": DOC},
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_ocr_upstream_error(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch(
        "ai_api.proxy.upstream.aocr",
        new=AsyncMock(side_effect=RuntimeError("DeploymentNotFound")),
    ):
        r = await app_client.post(
            "/v1/ocr", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": OCR, "document": DOC},
        )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "upstream_error"
    rec = await _last_record(CallOutcome.upstream_error)
    assert rec is not None and rec.allocation_id == alloc["id"]
