"""Phase 11 T024: calculate_cost with cached-input discount + reasoning inclusion."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ai_api.services.pricing import Price, calculate_cost


def _price(inp: str, out: str, cached: str | None) -> Price:
    return Price(
        input_per_1k=Decimal(inp),
        output_per_1k=Decimal(out),
        provider="azure",
        model="gpt-5",
        effective_from=datetime.now(UTC),
        cached_input_per_1k=Decimal(cached) if cached is not None else None,
    )


def test_cost_with_cached_discount() -> None:
    # 1000 input (200 cached), 500 output. input=1.0/1k, output=2.0/1k, cached=0.25/1k
    cost = calculate_cost(
        price=_price("1.0", "2.0", "0.25"),
        prompt_tokens=1000,
        completion_tokens=500,
        cached_tokens=200,
    )
    # full input 800*1.0/1k=0.8 + cached 200*0.25/1k=0.05 + output 500*2.0/1k=1.0
    assert cost == Decimal("1.85")


def test_cost_cached_without_cached_price_falls_back_to_input() -> None:
    cost = calculate_cost(
        price=_price("1.0", "2.0", None),
        prompt_tokens=1000,
        completion_tokens=0,
        cached_tokens=200,
    )
    # cached billed at full input price → 1000*1.0/1k = 1.0
    assert cost == Decimal("1.0")


def test_reasoning_not_double_counted() -> None:
    # completion already includes reasoning; cost only uses completion total.
    cost = calculate_cost(
        price=_price("0", "3.0", None),
        prompt_tokens=0,
        completion_tokens=100,  # includes e.g. 60 reasoning
        cached_tokens=0,
    )
    assert cost == Decimal("0.300")


def test_no_price_returns_none() -> None:
    assert calculate_cost(price=None, prompt_tokens=10, completion_tokens=10) is None
