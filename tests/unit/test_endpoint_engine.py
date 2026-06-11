"""Phase 31 (042): unit tests for the endpoint engine's pure pieces (Meters)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ai_api.proxy.endpoint_spec import EndpointSpec, TokenMeter, UnitMeter
from ai_api.services.pricing import Price


def _token_price() -> Price:
    return Price(
        input_per_1k=Decimal("0.005"), output_per_1k=Decimal("0.015"),
        provider="azure", model="m", effective_from=datetime.now(UTC),
    )


def _unit_price(unit: str, per: str) -> Price:
    return Price(
        input_per_1k=Decimal(0), output_per_1k=Decimal(0),
        provider="azure", model="m", effective_from=datetime.now(UTC),
        price_unit=unit, price_per_unit=Decimal(per),
    )


def test_token_meter_reads_usage() -> None:
    m = TokenMeter().measure({}, {"usage": {"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000}}, _token_price())
    assert m.record_kwargs["prompt_tokens"] == 1000
    assert m.record_kwargs["total_tokens"] == 2000
    assert m.cost == Decimal("0.020")  # 1k in @0.005 + 1k out @0.015


def test_token_meter_no_price_none_cost() -> None:
    m = TokenMeter().measure({}, {"usage": {"prompt_tokens": 5}}, None)
    assert m.cost is None and m.record_kwargs["prompt_tokens"] == 5


def test_unit_meter_quantity_from_payload() -> None:
    meter = UnitMeter("image", lambda f, p: len(p.get("data") or []))
    m = meter.measure({}, {"data": [1, 2, 3]}, _unit_price("image", "0.04"))
    assert m.record_kwargs == {"quantity": 3, "unit": "image"}
    assert m.cost == Decimal("0.12")  # 3 x 0.04


def test_unit_meter_quantity_from_fields() -> None:
    # TTS-style: quantity from the request fields, not the response
    meter = UnitMeter("character", lambda f, p: len(f["input"]))
    m = meter.measure({"input": "hello"}, {}, _unit_price("character", "0.001"))
    assert m.record_kwargs == {"quantity": 5, "unit": "character"}
    assert m.cost == Decimal("0.005")


def test_unit_meter_wrong_unit_price_is_zero() -> None:
    # price is for "page" but meter is "query" → no matching per-unit price → 0
    meter = UnitMeter("query", lambda f, p: 1)
    m = meter.measure({}, {}, _unit_price("page", "0.003"))
    assert m.cost == Decimal(0)


def test_endpoint_spec_defaults() -> None:
    spec = EndpointSpec(path="/x", call=lambda f, r, m: None, meter=TokenMeter())
    assert spec.input_shape == "json" and spec.output_shape == "json"
    assert spec.required == () and spec.model_field == "model"
