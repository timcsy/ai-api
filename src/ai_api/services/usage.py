"""Usage aggregation service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import (
    Allocation,
    CallOutcome,
    CallRecord,
    Member,
    MemberTag,
)

GroupBy = Literal["member", "allocation", "model", "tag"]
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
    # Phase 11: Responses API token breakdown (subsets of prompt/completion).
    reasoning_tokens: int = 0
    cached_tokens: int = 0


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
    member_id: str | None = None,
) -> list[UsageItem]:
    sum_total = func.coalesce(func.sum(CallRecord.total_tokens), 0).label("total")
    sum_prompt = func.coalesce(func.sum(CallRecord.prompt_tokens), 0).label("prompt")
    sum_completion = func.coalesce(func.sum(CallRecord.completion_tokens), 0).label("completion")
    sum_cost = func.coalesce(func.sum(CallRecord.cost_usd), 0).label("cost")
    sum_reasoning = func.coalesce(func.sum(CallRecord.reasoning_tokens), 0).label("reasoning")
    sum_cached = func.coalesce(func.sum(CallRecord.cached_tokens), 0).label("cached")
    cnt = func.count().label("cnt")

    base_filters = [
        CallRecord.outcome == CallOutcome.success,
        CallRecord.started_at >= from_,
        CallRecord.started_at < to,
    ]
    # Phase 018: member-scope. All three branches join Allocation, so adding the
    # filter here scopes every group_by to this member. None = existing (admin)
    # behaviour, unchanged.
    if member_id is not None:
        base_filters.append(Allocation.member_id == member_id)

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
                sum_reasoning,
                sum_cached,
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
                reasoning_tokens=int(r[8] or 0),
                cached_tokens=int(r[9] or 0),
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
                sum_reasoning,
                sum_cached,
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
                reasoning_tokens=int(r[8] or 0),
                cached_tokens=int(r[9] or 0),
            )
            for r in alloc_rows
        ]

    if group_by == "tag":
        # Phase 15: aggregate by MemberTag.tag. JOIN member_tags so a member in
        # N tags contributes to each (intended overlap — a tag total = sum of its
        # members' usage; a member in two tags counts in both). Independent
        # variable names per the multi-branch-select type lesson.
        tag_stmt = (
            select(
                MemberTag.tag,
                sum_total,
                sum_prompt,
                sum_completion,
                sum_cost,
                cnt,
                sum_reasoning,
                sum_cached,
            )
            .join(Allocation, Allocation.id == CallRecord.allocation_id)
            .join(MemberTag, MemberTag.member_id == Allocation.member_id)
            .where(*base_filters)
            .group_by(MemberTag.tag)
            .order_by(sum_total.desc())
        )
        if service_only:
            tag_stmt = tag_stmt.where(Allocation.is_service_allocation.is_(True))
        tag_rows = (await db.execute(tag_stmt)).all()
        return [
            UsageItem(
                group_key=r[0],
                display_name=r[0],
                total_tokens=int(r[1] or 0),
                prompt_tokens=int(r[2] or 0),
                completion_tokens=int(r[3] or 0),
                total_cost_usd=Decimal(r[4] or 0),
                call_count=int(r[5]),
                reasoning_tokens=int(r[6] or 0),
                cached_tokens=int(r[7] or 0),
            )
            for r in tag_rows
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
            sum_reasoning,
            sum_cached,
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
            reasoning_tokens=int(r[6] or 0),
            cached_tokens=int(r[7] or 0),
        )
        for r in model_rows
    ]


async def aggregate_usage_for_tag_members(
    db: AsyncSession,
    *,
    tag: str,
    from_: datetime,
    to: datetime,
    service_only: bool = False,
) -> list[UsageItem]:
    """Phase 15 drill-down: per-member usage for members belonging to `tag`.

    Reuses the member-dimension aggregation, scoped to members that carry the
    given tag. Returns the same UsageItem shape as group_by=member.
    """
    sum_total = func.coalesce(func.sum(CallRecord.total_tokens), 0).label("total")
    sum_prompt = func.coalesce(func.sum(CallRecord.prompt_tokens), 0).label("prompt")
    sum_completion = func.coalesce(func.sum(CallRecord.completion_tokens), 0).label("completion")
    sum_cost = func.coalesce(func.sum(CallRecord.cost_usd), 0).label("cost")
    sum_reasoning = func.coalesce(func.sum(CallRecord.reasoning_tokens), 0).label("reasoning")
    sum_cached = func.coalesce(func.sum(CallRecord.cached_tokens), 0).label("cached")
    cnt = func.count().label("cnt")

    tag_member_ids = select(MemberTag.member_id).where(MemberTag.tag == tag)

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
            sum_reasoning,
            sum_cached,
        )
        .join(Allocation, Allocation.id == CallRecord.allocation_id)
        .join(Member, Member.id == Allocation.member_id)
        .where(
            CallRecord.outcome == CallOutcome.success,
            CallRecord.started_at >= from_,
            CallRecord.started_at < to,
            Allocation.member_id.in_(tag_member_ids),
        )
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
            reasoning_tokens=int(r[8] or 0),
            cached_tokens=int(r[9] or 0),
        )
        for r in rows
    ]


async def count_unpriced_calls(
    db: AsyncSession,
    *,
    member_id: str,
    from_: datetime,
    to: datetime,
) -> int:
    """Count a member's successful calls that consumed tokens but recorded no
    cost (model had no price at call time). Drives the `has_unpriced` flag so the
    UI can mark the cost summary as an under-estimate (FR-006)."""
    stmt = (
        select(func.count())
        .select_from(CallRecord)
        .join(Allocation, Allocation.id == CallRecord.allocation_id)
        .where(
            CallRecord.outcome == CallOutcome.success,
            CallRecord.started_at >= from_,
            CallRecord.started_at < to,
            Allocation.member_id == member_id,
            CallRecord.total_tokens > 0,
            or_(CallRecord.cost_usd.is_(None), CallRecord.cost_usd == 0),
        )
    )
    return int(await db.scalar(stmt) or 0)


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
