"""Phase 7 / US1+US2+US3: admin price list view + history + add version.

Contract: specs/016-price-list-admin/contracts/admin-prices.yaml
Reuses the existing price_list table (no schema change).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.services import pricing

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


@router.get("/prices")
async def list_prices(session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    return await pricing.list_catalog_prices(session, datetime.now(UTC))


@router.get("/prices/history")
async def price_history(
    provider: str = Query(...),
    model: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    return await pricing.list_history(session, provider, model)


class PriceCreateRequest(BaseModel):
    provider: str
    model: str
    input_per_1k: str
    output_per_1k: str
    cached_input_per_1k: str | None = None
    # Phase 29 ②: non-token unit price (e.g. price_unit="page"). If price_unit is
    # given, price_per_unit is required.
    price_unit: str | None = None
    price_per_unit: str | None = None
    effective_from: datetime
    source_note: str | None = None


@router.post("/prices", status_code=status.HTTP_201_CREATED)
async def create_price(
    payload: PriceCreateRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if payload.price_unit and not payload.price_per_unit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_err("bad_request", "price_unit requires price_per_unit"),
        )
    try:
        return await pricing.create_version(
            session,
            provider=payload.provider,
            model=payload.model,
            input_per_1k=payload.input_per_1k,
            output_per_1k=payload.output_per_1k,
            cached_input_per_1k=payload.cached_input_per_1k,
            price_unit=payload.price_unit,
            price_per_unit=payload.price_per_unit,
            effective_from=payload.effective_from,
            source_note=payload.source_note,
        )
    except pricing.InvalidPriceError as exc:
        raise HTTPException(status_code=422, detail=_err("invalid_price", str(exc))) from exc
    except pricing.DuplicateVersionError as exc:
        raise HTTPException(status_code=409, detail=_err("duplicate_version", str(exc))) from exc
