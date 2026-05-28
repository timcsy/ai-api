"""Phase 11 T025/T026: /v1/responses precise billing (reasoning/cached) + unpriced."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord, ModelCatalog, PriceList

RESP_MODEL = "azure/gpt-5"


async def _seed(client: AsyncClient, admin_headers: dict[str, str], *, with_price: bool) -> dict:
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
        if with_price:
            s.add(PriceList(
                id=str(ULID()), provider="azure", model="gpt-5",
                input_per_1k_tokens_usd=Decimal("1.0"),
                output_per_1k_tokens_usd=Decimal("2.0"),
                cached_input_per_1k_tokens_usd=Decimal("0.25"),
                effective_from=now - timedelta(days=1), created_at=now, created_by="test",
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


def _stub() -> dict:
    return {
        "id": "resp_b", "object": "response", "output": [],
        "usage": {
            "input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500,
            "output_tokens_details": {"reasoning_tokens": 300},
            "input_tokens_details": {"cached_tokens": 200},
        },
    }


@pytest.mark.asyncio
async def test_billing_with_reasoning_and_cached(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _seed(app_client, admin_headers, with_price=True)
    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RESP_MODEL, "input": "hi"},
        )
    assert r.status_code == 200, r.text
    sm = get_sessionmaker()
    async with sm() as s:
        rec = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
        )).scalar_one()
    assert rec.reasoning_tokens == 300
    assert rec.cached_tokens == 200
    # full input 800*1.0/1k=0.8 + cached 200*0.25/1k=0.05 + output 500*2.0/1k=1.0 = 1.85
    assert rec.cost_usd == Decimal("1.850000")


@pytest.mark.asyncio
async def test_billing_unpriced_records_null_cost(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _seed(app_client, admin_headers, with_price=False)
    with patch("ai_api.proxy.upstream.aresponses", new=AsyncMock(return_value=_stub())):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RESP_MODEL, "input": "hi"},
        )
    assert r.status_code == 200, r.text
    sm = get_sessionmaker()
    async with sm() as s:
        rec = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
        )).scalar_one()
    assert rec.cost_usd is None
    assert rec.reasoning_tokens == 300  # usage still recorded
