"""Pricing service: point-in-time lookup + cost calculation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import PriceList


@dataclass(frozen=True)
class Price:
    input_per_1k: Decimal
    output_per_1k: Decimal
    provider: str
    model: str
    effective_from: datetime


async def lookup_price_for_call(
    db: AsyncSession, *, provider: str, model: str, call_time: datetime
) -> Price | None:
    """Return the PriceList row in effect at `call_time`, else None."""
    stmt = (
        select(PriceList)
        .where(
            PriceList.provider == provider,
            PriceList.model == model,
            PriceList.effective_from <= call_time,
        )
        .order_by(PriceList.effective_from.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return Price(
        input_per_1k=row.input_per_1k_tokens_usd,
        output_per_1k=row.output_per_1k_tokens_usd,
        provider=row.provider,
        model=row.model,
        effective_from=row.effective_from,
    )


def calculate_cost(
    *,
    price: Price | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> Decimal | None:
    """Compute USD cost. Returns None when no price is available."""
    if price is None:
        return None
    pt = Decimal(prompt_tokens or 0)
    ct = Decimal(completion_tokens or 0)
    return ((pt / Decimal(1000)) * price.input_per_1k) + (
        (ct / Decimal(1000)) * price.output_per_1k
    )
