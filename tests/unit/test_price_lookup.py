"""Unit tests for pricing service."""
from __future__ import annotations

from decimal import Decimal

from ai_api.services.pricing import Price, calculate_cost


def _price(input_rate: str = "0.000150", output_rate: str = "0.000600") -> Price:
    from datetime import UTC, datetime

    return Price(
        input_per_1k=Decimal(input_rate),
        output_per_1k=Decimal(output_rate),
        provider="azure",
        model="gpt-4o-mini",
        effective_from=datetime(2026, 5, 1, tzinfo=UTC),
    )


def test_calculate_cost_basic():
    cost = calculate_cost(price=_price(), prompt_tokens=1000, completion_tokens=500)
    # 1000/1000 * 0.000150 + 500/1000 * 0.000600 = 0.000150 + 0.000300 = 0.000450
    assert cost == Decimal("0.000450")


def test_calculate_cost_zero_tokens():
    assert calculate_cost(price=_price(), prompt_tokens=0, completion_tokens=0) == Decimal("0")


def test_calculate_cost_none_tokens_treated_as_zero():
    assert calculate_cost(price=_price(), prompt_tokens=None, completion_tokens=None) == Decimal("0")


def test_calculate_cost_no_price_is_none():
    assert calculate_cost(price=None, prompt_tokens=1000, completion_tokens=500) is None
