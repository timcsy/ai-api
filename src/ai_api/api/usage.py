"""Admin usage + billing endpoints."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.models import AuditEventType, AuthAuditLog
from ai_api.services.allocations import AllocationService
from ai_api.services.usage import (
    Bucket,
    GroupBy,
    aggregate_usage,
    aggregate_usage_for_tag_members,
    usage_heatmap,
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


@router.get("/usage/tag/{tag}/members")
async def get_tag_members(
    tag: str,
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    service_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Phase 15 drill-down: per-member usage for members belonging to `tag`."""
    _validate_range(from_, to)
    items = await aggregate_usage_for_tag_members(
        session, tag=tag, from_=from_, to=to, service_only=service_only
    )
    return {
        "tag": tag,
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "members": _serialize_items(items),
    }


@router.get("/usage/timeseries")
async def get_platform_timeseries(
    bucket: Bucket = Query(...),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Phase 14: platform-wide timeseries — all allocations summed per bucket."""
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
    points = await usage_timeseries(session, bucket=bucket, from_=from_, to=to)
    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
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


@router.get("/allocations/{allocation_id}/quarantine-reason")
async def get_quarantine_reason(
    allocation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Phase 14 (US4): why an allocation was quarantined/paused, from the latest
    relevant audit event's details. Surfaces the same numbers the anomaly
    detector logged so admins don't have to dig through the audit trail."""
    if await AllocationService(session).get(allocation_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "allocation not found"}},
        )
    stmt = (
        select(AuthAuditLog)
        .where(
            AuthAuditLog.target_type == "allocation",
            AuthAuditLog.target_id == allocation_id,
            AuthAuditLog.event_type.in_(
                [
                    AuditEventType.allocation_quarantined,
                    AuditEventType.allocation_paused,
                ]
            ),
        )
        .order_by(AuthAuditLog.created_at.desc())
        .limit(1)
    )
    event = (await session.execute(stmt)).scalars().first()

    if event is None:
        return {
            "allocation_id": allocation_id,
            "event_type": None,
            "reason": None,
            "last_hour_calls": None,
            "baseline_per_hour": None,
            "occurred_at": None,
            "message": "原因未記錄",
        }

    details = event.details or {}
    last_hour_calls = details.get("last_hour_calls")
    baseline_per_hour = details.get("baseline_per_hour")
    reason = details.get("reason")

    if last_hour_calls is None and baseline_per_hour is None:
        # FR-017: legacy event without details — don't error, just say so.
        message = "原因未記錄"
    else:
        verb = "暫停" if event.event_type == AuditEventType.allocation_paused else "隔離"
        baseline_txt = (
            f"{baseline_per_hour:g}" if isinstance(baseline_per_hour, (int, float)) else "未知"
        )
        message = (
            f"過去 1 小時 {last_hour_calls} 次呼叫，"
            f"基準約 {baseline_txt}/小時，已自動{verb}"
        )

    return {
        "allocation_id": allocation_id,
        "event_type": event.event_type.value,
        "reason": reason,
        "last_hour_calls": last_hour_calls,
        "baseline_per_hour": baseline_per_hour,
        "occurred_at": event.created_at.isoformat() if event.created_at else None,
        "message": message,
    }


@router.get("/usage/heatmap")
async def get_usage_heatmap(
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Phase 14: weekday x hour usage heatmap (UTC+8)."""
    _validate_range(from_, to)
    cells = await usage_heatmap(session, from_=from_, to=to)
    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "timezone": "UTC+8",
        "cells": [
            {
                "weekday": c.weekday,
                "hour": c.hour,
                "tokens": c.tokens,
                "call_count": c.call_count,
            }
            for c in cells
        ],
    }


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
