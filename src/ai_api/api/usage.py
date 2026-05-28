"""Admin usage + billing endpoints."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.services.allocations import AllocationService
from ai_api.services.usage import (
    Bucket,
    GroupBy,
    aggregate_usage,
    usage_timeseries,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])

MAX_RANGE = timedelta(days=90)


def _validate_range(from_: datetime, to: datetime) -> None:
    if from_ >= to:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_time_range",
                    "message": "`from` must be earlier than `to`",
                }
            },
        )
    if (to - from_) > MAX_RANGE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "range_too_wide",
                    "message": "time range must be ≤ 90 days",
                }
            },
        )


def _serialize_items(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        d: dict[str, Any] = {
            "group_key": it.group_key,
            "display_name": it.display_name,
            "total_tokens": it.total_tokens,
            "prompt_tokens": it.prompt_tokens,
            "completion_tokens": it.completion_tokens,
            "reasoning_tokens": it.reasoning_tokens,
            "cached_tokens": it.cached_tokens,
            "total_cost_usd": float(it.total_cost_usd),
            "call_count": it.call_count,
        }
        if it.is_service_allocation is not None:
            d["is_service_allocation"] = it.is_service_allocation
        out.append(d)
    return out


@router.get("/usage")
async def get_usage(
    group_by: GroupBy = Query(...),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    service_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _validate_range(from_, to)
    items = await aggregate_usage(
        session, group_by=group_by, from_=from_, to=to, service_only=service_only
    )
    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "group_by": group_by,
        "items": _serialize_items(items),
    }


@router.get("/usage.json")
async def get_usage_json(
    group_by: GroupBy = Query(...),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    service_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    _validate_range(from_, to)
    items = await aggregate_usage(
        session, group_by=group_by, from_=from_, to=to, service_only=service_only
    )
    return _serialize_items(items)


@router.get("/usage.csv")
async def get_usage_csv(
    group_by: GroupBy = Query(...),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    service_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    _validate_range(from_, to)
    items = await aggregate_usage(
        session, group_by=group_by, from_=from_, to=to, service_only=service_only
    )

    def _gen():  # type: ignore[no-untyped-def]
        buf = io.StringIO()
        writer = csv.writer(buf)
        headers = [
            "group_key",
            "display_name",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "cached_tokens",
            "total_cost_usd",
            "call_count",
        ]
        if group_by == "allocation":
            headers.append("is_service_allocation")
        writer.writerow(headers)
        # UTF-8 BOM so Excel opens nicely
        yield "﻿" + buf.getvalue()
        buf.seek(0)
        buf.truncate()
        for it in items:
            row = [
                it.group_key,
                it.display_name or "",
                it.total_tokens,
                it.prompt_tokens,
                it.completion_tokens,
                it.reasoning_tokens,
                it.cached_tokens,
                float(it.total_cost_usd),
                it.call_count,
            ]
            if group_by == "allocation":
                row.append(it.is_service_allocation)
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    return StreamingResponse(_gen(), media_type="text/csv")  # type: ignore[no-untyped-call]


@router.get("/allocations/{allocation_id}/usage-timeseries")
async def get_allocation_timeseries(
    allocation_id: str,
    bucket: Bucket = Query(...),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _validate_range(from_, to)
    if bucket == "hour" and (to - from_) > timedelta(days=7):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "range_too_wide_for_bucket",
                    "message": "bucket=hour requires range ≤ 7 days",
                }
            },
        )
    if await AllocationService(session).get(allocation_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    points = await usage_timeseries(
        session, allocation_id=allocation_id, bucket=bucket, from_=from_, to=to
    )
    return {
        "allocation_id": allocation_id,
        "bucket": bucket,
        "points": [
            {
                "ts": p.ts.isoformat() if hasattr(p.ts, "isoformat") else str(p.ts),
                "tokens": p.tokens,
                "cost_usd": float(p.cost_usd),
                "call_count": p.call_count,
            }
            for p in points
        ],
    }
