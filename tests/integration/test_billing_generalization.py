"""Phase 29 ② (040): billing generalization must NOT regress token billing, and
CallRecord must persist the new (quantity, unit) dimension for non-token calls."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord
from ai_api.services.pricing import Price, calculate_cost
from ai_api.services.records import RecordsService


def test_token_cost_unchanged() -> None:
    """Token cost math is byte-identical to before (calculate_cost untouched)."""
    price = Price(
        input_per_1k=Decimal("0.005"), output_per_1k=Decimal("0.015"),
        provider="azure", model="gpt-4o", effective_from=datetime.now(UTC),
    )
    cost = calculate_cost(price=price, prompt_tokens=1000, completion_tokens=1000)
    # 1k input @0.005 + 1k output @0.015 = 0.02
    assert cost == Decimal("0.020")
    assert calculate_cost(price=None, prompt_tokens=10, completion_tokens=10) is None


@pytest.mark.asyncio
async def test_record_call_persists_quantity_and_unit(app_client: AsyncClient) -> None:
    sm = get_sessionmaker()
    rid = str(ULID())
    async with sm() as s:
        await RecordsService(s).record_call(
            request_id=rid, allocation_id=None, subject="x@x.com",
            model="azure_ai/mistral-document-ai", started_at=datetime.now(UTC),
            status_code=200, outcome=CallOutcome.success,
            quantity=3, unit="page", cost_usd=Decimal("0.009"),
        )
        await s.commit()
    async with sm() as s:
        row = (await s.execute(
            select(CallRecord).where(CallRecord.request_id == rid)
        )).scalar_one()
        assert row.unit == "page"
        assert row.quantity == 3
        assert row.cost_usd == Decimal("0.009")
        # token columns stay empty for a page-billed call
        assert row.prompt_tokens is None
        assert row.total_tokens is None
