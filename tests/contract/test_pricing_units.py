"""Phase 29 ② (040): billing generalization — non-token units (page).

calculate_unit_cost + lookup carrying per-unit price + point-in-time selection.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import PriceList
from ai_api.services.pricing import calculate_unit_cost, lookup_price_for_call


def test_calculate_unit_cost_basic() -> None:
    assert calculate_unit_cost(3, Decimal("0.003")) == Decimal("0.009")
    # missing quantity or price → 0 (unpriced convention)
    assert calculate_unit_cost(None, Decimal("0.003")) == Decimal(0)
    assert calculate_unit_cost(3, None) == Decimal(0)
    assert calculate_unit_cost(0, Decimal("0.003")) == Decimal(0)


async def _seed_page_price(provider: str, model: str, when: datetime, per_page: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider=provider, model=model,
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="page", price_per_unit_usd=Decimal(per_page),
            effective_from=when, created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_lookup_carries_per_unit(app_client: AsyncClient) -> None:
    now = datetime.now(UTC)
    await _seed_page_price("azure_ai", "mistral-document-ai", now - timedelta(days=1), "0.003")
    sm = get_sessionmaker()
    async with sm() as s:
        price = await lookup_price_for_call(
            s, provider="azure_ai", model="mistral-document-ai", call_time=now
        )
    assert price is not None
    assert price.price_unit == "page"
    assert price.price_per_unit == Decimal("0.003")


@pytest.mark.asyncio
async def test_per_unit_point_in_time(app_client: AsyncClient) -> None:
    base = datetime.now(UTC) - timedelta(days=10)
    await _seed_page_price("azure_ai", "ocr-x", base, "0.003")
    await _seed_page_price("azure_ai", "ocr-x", base + timedelta(days=5), "0.005")
    sm = get_sessionmaker()
    async with sm() as s:
        early = await lookup_price_for_call(
            s, provider="azure_ai", model="ocr-x", call_time=base + timedelta(days=1)
        )
        late = await lookup_price_for_call(
            s, provider="azure_ai", model="ocr-x", call_time=base + timedelta(days=6)
        )
    assert early is not None and early.price_per_unit == Decimal("0.003")
    assert late is not None and late.price_per_unit == Decimal("0.005")


@pytest.mark.asyncio
async def test_current_price_map_surfaces_per_unit(app_client: AsyncClient) -> None:
    """Phase 29②/③ fix: catalog display source must carry the non-token unit price
    (was a missed sink — admin model detail showed 'per-1M / 未定價' for OCR)."""
    from datetime import datetime as _dt

    from ai_api.services.pricing import current_price_map
    await _seed_page_price("azure_ai", "doc-ocr", _dt.now(UTC) - timedelta(days=1), "0.003")
    sm = get_sessionmaker()
    async with sm() as s:
        pm = await current_price_map(s, _dt.now(UTC))
    entry = pm[("azure_ai", "doc-ocr")]
    assert entry["price_unit"] == "page"
    assert Decimal(entry["price_per_unit"]) == Decimal("0.003")


@pytest.mark.asyncio
async def test_minute_unit_for_realtime(app_client: AsyncClient) -> None:
    """Phase 32: realtime transcription bills per-minute — same unit-billing path,
    `minute` is just a new string unit value (no schema change)."""
    now = datetime.now(UTC)
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(PriceList(
            id=str(ULID()), provider="azure", model="gpt-realtime-whisper",
            input_per_1k_tokens_usd=Decimal(0), output_per_1k_tokens_usd=Decimal(0),
            price_unit="minute", price_per_unit_usd=Decimal("0.017"),
            effective_from=now - timedelta(days=1), created_at=datetime.now(UTC), created_by="test",
        ))
        await s.commit()
        price = await lookup_price_for_call(
            s, provider="azure", model="gpt-realtime-whisper", call_time=now
        )
    assert price is not None and price.price_unit == "minute"
    # 5 minutes x $0.017 = $0.085 (per-minute billing through the existing path)
    assert calculate_unit_cost(5, price.price_per_unit) == Decimal("0.085")
