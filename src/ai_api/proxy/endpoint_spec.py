"""Phase 31 (042): data-driven endpoint architecture — three orthogonal axes.

A member inference endpoint differs from another only in three independent ways:
  ① I/O shape   — how to read the request / shape the response (json/multipart x json/binary)
  ② Meter       — how to bill (token via usage, or a non-token unit + quantity fn)
  ③ call        — how to map parsed fields onto the litellm upstream function

`EndpointSpec` is one row of data describing those three for one endpoint. The
shared engine (engine.py) runs the unchanging flow; adding a same-shape endpoint
is adding one EndpointSpec — no new flow code.

NOTE: streaming endpoints (/chat/completions, /responses) are NOT modelled here
— their billing happens mid-stream (Phase 11), a different execution shape; they
keep their own handlers.
"""
from __future__ import annotations

import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ai_api.services.pricing import Price, calculate_cost, calculate_unit_cost


def creds(resolved: Any) -> dict[str, Any]:
    """The upstream credential kwargs every wrapper takes."""
    return {
        "api_key": resolved.api_key,
        "api_base": resolved.base_url,
        "api_version": (resolved.extra_config or {}).get("api_version"),
    }


class InputShape(enum.StrEnum):
    json = "json"          # await request.json(); model in body
    multipart = "multipart"  # await request.form(); model in form, files → (name, bytes)


class OutputShape(enum.StrEnum):
    json = "json"      # return the payload dict
    binary = "binary"  # return Response(bytes, media_type)


@dataclass(frozen=True)
class Metering:
    """Result of measuring one call: the cost + the record_call kwargs."""
    cost: Decimal | None
    record_kwargs: dict[str, Any]


class TokenMeter:
    """Bill on the response's token usage (chat-style). unit stays NULL."""

    def measure(self, fields: dict[str, Any], payload: dict[str, Any], price: Price | None) -> Metering:
        usage = payload.get("usage") or {}
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens") or 0
        tt = usage.get("total_tokens")
        cost = calculate_cost(price=price, prompt_tokens=pt, completion_tokens=ct)
        return Metering(cost, {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt})


class UnitMeter:
    """Bill on a non-token unit (page/query/character/image…) x per-unit price."""

    def __init__(self, unit: str, quantity_fn: Callable[[dict[str, Any], dict[str, Any]], int | None]) -> None:
        self.unit = unit
        self.quantity_fn = quantity_fn

    def measure(self, fields: dict[str, Any], payload: dict[str, Any], price: Price | None) -> Metering:
        quantity = self.quantity_fn(fields, payload)
        per_unit = price.price_per_unit if price is not None and price.price_unit == self.unit else None
        cost = calculate_unit_cost(quantity, per_unit)
        return Metering(cost, {"quantity": quantity, "unit": self.unit})


Meter = TokenMeter | UnitMeter
# call: (fields, resolved, upstream_model) -> awaitable upstream result
CallFn = Callable[[dict[str, Any], Any, str], Awaitable[Any]]


@dataclass(frozen=True)
class EndpointSpec:
    path: str                       # "/embeddings", "/audio/speech", …
    call: CallFn                    # maps parsed fields → litellm wrapper
    meter: Meter                    # TokenMeter() | UnitMeter(unit, qty_fn)
    input_shape: InputShape = InputShape.json
    output_shape: OutputShape = OutputShape.json
    required: tuple[str, ...] = ()  # fields validated after parse (missing → 400)
    model_field: str = "model"      # where the model id lives in the request
    binary_media_type: str = "audio/mpeg"
    label: str = field(default="")  # optional human label
