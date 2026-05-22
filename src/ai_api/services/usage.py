"""Usage aggregation service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import (
    Allocation,
    CallOutcome,
    CallRecord,
    Member,
)

GroupBy = Literal["member", "allocation", "model"]
Bucket = Literal["hour", "day"]


@dataclass(frozen=True)
class UsageItem:
    group_key: str
    display_name: str | None
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: Decimal
    call_count: int
    is_service_allocation: bool | None = None


@dataclass(frozen=True)
class TimeseriesPoint:
    ts: datetime
    tokens: int
    cost_usd: Decimal
    call_count: int


async def aggregate_usage(
    db: AsyncSession,
    *,
    group_by: GroupBy,
    from_: datetime,
    to: datetime,
    service_only: bool = False,
) -> list[UsageItem]:
    sum_total = func.coalesce(func.sum(CallRecord.total_tokens), 0).label("total")
    sum_prompt = func.coalesce(func.sum(CallRecord.prompt_tokens), 0).label("prompt")
    sum_completion = func.coalesce(func.sum(CallRecord.completion_tokens), 0).label("completion")
    sum_cost = func.coalesce(func.sum(CallRecord.cost_usd), 0).label("cost")
    cnt = func.count().label("cnt")

    base_filters = [
        CallRecord.outcome == CallOutcome.success,
        CallRecord.started_at >= from_,
        CallRecord.started_at < to,
    ]

    if group_by == "member":
        stmt = (
            select(
                Member.id,
                Member.email,
                Member.display_name,
                sum_total,
                sum_prompt,
                sum_completion,
                sum_cost,
                cnt,
            )
            .join(Allocation, Allocation.id == CallRecord.allocation_id)
            .join(Member, Member.id == Allocation.member_id)
            .where(*base_filters)
            .group_by(Member.id, Member.email, Member.display_name)
            .order_by(sum_total.desc())
        )
        if service_only:
            stmt = stmt.where(Allocation.is_service_allocation.is_(True))
        rows = (await db.execute(stmt)).all()
        return [
            UsageItem(
                group_key=r[0],
                display_name=r[2] or r[1],
                total_tokens=int(r[3] or 0),
                prompt_tokens=int(r[4] or 0),
                completion_tokens=int(r[5] or 0),
                total_cost_usd=Decimal(r[6] or 0),
                call_count=int(r[7]),
            )
            for r in rows
        ]

    if group_by == "allocation":
        alloc_stmt = (
            select(
                Allocation.id,
                Allocation.subject_snapshot,
                Allocation.is_service_allocation,
                sum_total,
                sum_prompt,
                sum_completion,
                sum_cost,
                cnt,
            )
            .join(CallRecord, CallRecord.allocation_id == Allocation.id)
            .where(*base_filters)
            .group_by(Allocation.id, Allocation.subject_snapshot, Allocation.is_service_allocation)
            .order_by(sum_total.desc())
        )
        if service_only:
            alloc_stmt = alloc_stmt.where(Allocation.is_service_allocation.is_(True))
        alloc_rows = (await db.execute(alloc_stmt)).all()
        return [
            UsageItem(
                group_key=r[0],
                display_name=r[1],
                total_tokens=int(r[3] or 0),
                prompt_tokens=int(r[4] or 0),
                completion_tokens=int(r[5] or 0),
                total_cost_usd=Decimal(r[6] or 0),
                call_count=int(r[7]),
                is_service_allocation=bool(r[2]),
            )
            for r in alloc_rows
        ]

    # group_by == "model"
    model_stmt = (
        select(
            CallRecord.model,
            sum_total,
            sum_prompt,
            sum_completion,
            sum_cost,
            cnt,
        )
        .join(Allocation, Allocation.id == CallRecord.allocation_id)
        .where(*base_filters)
        .group_by(CallRecord.model)
        .order_by(sum_total.desc())
    )
    if service_only:
        model_stmt = model_stmt.where(Allocation.is_service_allocation.is_(True))
    model_rows = (await db.execute(model_stmt)).all()
    return [
        UsageItem(
            group_key=r[0] or "(none)",
            display_name=r[0],
            total_tokens=int(r[1] or 0),
            prompt_tokens=int(r[2] or 0),
            completion_tokens=int(r[3] or 0),
            total_cost_usd=Decimal(r[4] or 0),
            call_count=int(r[5]),
        )
        for r in model_rows
    ]


async def usage_timeseries(
    db: AsyncSession,
    *,
    allocation_id: str,
    bucket: Bucket,
    from_: datetime,
    to: datetime,
) -> list[TimeseriesPoint]:
    # dialect-aware truncation
    dialect = db.bind.dialect.name if db.bind else "sqlite"
    if dialect == "postgresql":
        ts_expr = func.date_trunc(bucket, CallRecord.started_at)
    else:
        fmt = "%Y-%m-%d %H:00:00" if bucket == "hour" else "%Y-%m-%d 00:00:00"
        ts_expr = func.strftime(fmt, CallRecord.started_at)

    stmt = (
        select(
            ts_expr.label("ts"),
            func.coalesce(func.sum(CallRecord.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(CallRecord.cost_usd), 0).label("cost"),
            func.count().label("cnt"),
        )
        .where(
            CallRecord.allocation_id == allocation_id,
            CallRecord.outcome == CallOutcome.success,
            CallRecord.started_at >= from_,
            CallRecord.started_at < to,
        )
        .group_by(ts_expr)
        .order_by(ts_expr)
    )
    rows = (await db.execute(stmt)).all()
    out: list[TimeseriesPoint] = []
    for r in rows:
        ts_val = r[0]
        if isinstance(ts_val, str):
            ts_val = datetime.fromisoformat(ts_val.replace(" ", "T"))
        out.append(
            TimeseriesPoint(
                ts=ts_val,
                tokens=int(r[1] or 0),
                cost_usd=Decimal(r[2] or 0),
                call_count=int(r[3]),
            )
        )
    return out
