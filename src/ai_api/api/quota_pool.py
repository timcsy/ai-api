"""Admin endpoints for the adaptive quota pool (Phase 3c)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.auth import audit
from ai_api.models import (
    ActorType,
    Allocation,
    AllocationStatus,
    AuditEventType,
    RebalanceLog,
)
from ai_api.services.quota_pool import (
    PoolDisabledError,
    PoolExhaustedByReservedError,
    PoolIdleError,
    RebalanceConservationError,
    active_pool_member_count,
    apply_rebalance,
    get_pool_config,
    recent_month_usage,
    suggest_pool_config,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


class PoolConfigUpdate(BaseModel):
    total_tokens_per_month: int = Field(ge=0)
    floor_per_allocation: int = Field(ge=0)


@router.get("/quota-pool/status")
async def get_pool_status(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    # Phase 39: T/floor come from the DB singleton (single source of truth;
    # lazy-seeded from env on first read). This value == what apply_rebalance uses.
    cfg = await get_pool_config(session)
    T = cfg.total_tokens_per_month
    floor = cfg.floor_per_allocation

    service_stmt = select(
        func.coalesce(
            func.sum(func.coalesce(Allocation.quota_tokens_per_month, 0)),
            0,
        )
    ).where(
        Allocation.status == AllocationStatus.active,
        Allocation.is_service_allocation.is_(True),
    )
    locked_stmt = select(
        func.coalesce(
            func.sum(func.coalesce(Allocation.quota_tokens_per_month, 0)),
            0,
        )
    ).where(
        Allocation.status == AllocationStatus.active,
        Allocation.is_service_allocation.is_(False),
        Allocation.quota_locked.is_(True),
    )
    pool_count_stmt = select(func.count()).where(
        Allocation.status == AllocationStatus.active,
        Allocation.is_service_allocation.is_(False),
        Allocation.quota_locked.is_(False),
    )
    last_log_stmt = (
        select(RebalanceLog.finished_at).order_by(desc(RebalanceLog.finished_at)).limit(1)
    )

    service_reserved = int((await session.execute(service_stmt)).scalar_one() or 0)
    locked_reserved = int((await session.execute(locked_stmt)).scalar_one() or 0)
    pool_count = int((await session.execute(pool_count_stmt)).scalar_one() or 0)
    last_at = (await session.execute(last_log_stmt)).scalar_one_or_none()

    sugg = await suggest_pool_config(session)
    recent = sugg.recent_month_tokens
    # Soft warning (FR-006): current T below recent usage will start blocking users.
    warning = (
        f"目前總額 {T} 低於近月用量 {recent}，這會讓部分使用者本月被擋下。"
        if T > 0 and recent > T
        else None
    )

    return {
        "total_T": T,
        "reserved": {"service": service_reserved, "locked": locked_reserved},
        "distributable": T - service_reserved - locked_reserved,
        "pool_member_count": pool_count,
        "floor": floor,
        "settings": {"enabled": T > 0},
        "last_rebalance_at": last_at.isoformat() if last_at else None,
        # Phase 39: editable config + recommendation + soft warning.
        "config": {
            "total_tokens_per_month": cfg.total_tokens_per_month,
            "floor_per_allocation": cfg.floor_per_allocation,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
            "updated_by": cfg.updated_by,
        },
        "suggestion": {
            "recent_month_tokens": recent,
            "pool_members": sugg.pool_members,
            "suggested_total": sugg.suggested_total,
            "suggested_floor": sugg.suggested_floor,
        },
        "warning": warning,
    }


@router.put("/quota-pool/config")
async def update_pool_config(
    body: PoolConfigUpdate = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Set the quota-pool total T and per-allocation floor (Phase 39).

    Validation: T >= floor * N (else the pool can't even cover floors). T below
    recent usage is allowed but surfaced as a warning on GET status.
    """
    n = await active_pool_member_count(session)
    if body.total_tokens_per_month < body.floor_per_allocation * n:
        raise HTTPException(
            status_code=422,
            detail=_err(
                "invalid_pool_config",
                f"總額 {body.total_tokens_per_month} 不足以墊付每人保底"
                f"（保底 {body.floor_per_allocation} × {n} 人 = {body.floor_per_allocation * n}）。"
                f"請提高總額或降低保底。",
            ),
        )

    cfg = await get_pool_config(session)
    cfg.total_tokens_per_month = body.total_tokens_per_month
    cfg.floor_per_allocation = body.floor_per_allocation
    cfg.updated_at = datetime.now(UTC)
    cfg.updated_by = "admin"
    await audit.record(
        session,
        event_type=AuditEventType.pool_config_updated,
        actor_type=ActorType.admin,
        target_type="pool_config",
        target_id="1",
        details={
            "total_tokens_per_month": body.total_tokens_per_month,
            "floor_per_allocation": body.floor_per_allocation,
        },
    )
    await session.commit()
    recent = await recent_month_usage(session)
    return {
        "total_tokens_per_month": cfg.total_tokens_per_month,
        "floor_per_allocation": cfg.floor_per_allocation,
        "warning": (
            f"目前總額低於近月用量 {recent}，部分使用者本月可能被擋下。"
            if recent > cfg.total_tokens_per_month
            else None
        ),
    }


@router.post("/quota-pool/rebalance")
async def manual_rebalance(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        outcome = await apply_rebalance(session, trigger="admin:manual")
    except PoolDisabledError as exc:
        await session.commit()  # preserve audit
        raise HTTPException(status_code=409, detail=_err("pool_disabled", str(exc))) from exc
    except PoolExhaustedByReservedError as exc:
        await session.commit()
        raise HTTPException(
            status_code=409, detail=_err("pool_exhausted_by_reserved", str(exc))
        ) from exc
    except PoolIdleError as exc:
        await session.commit()
        raise HTTPException(status_code=409, detail=_err("pool_idle", str(exc))) from exc
    except RebalanceConservationError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail=_err("rebalance_failed", str(exc))
        ) from exc

    if outcome.log is None:
        return {"skipped": True, "reason": outcome.skipped_reason}
    return _log_to_summary(outcome.log)


@router.get("/quota-pool/rebalance-log")
async def list_rebalance_log(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(RebalanceLog).order_by(desc(RebalanceLog.started_at)).limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_log_to_summary(r) for r in rows]


@router.get("/quota-pool/rebalance-log/{log_id}")
async def get_rebalance_log(
    log_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    log = (
        await session.execute(select(RebalanceLog).where(RebalanceLog.id == log_id))
    ).scalar_one_or_none()
    if log is None:
        raise HTTPException(
            status_code=404,
            detail=_err("not_found", f"rebalance log {log_id} not found"),
        )
    out = _log_to_summary(log)
    out["details"] = log.details
    return out


def _log_to_summary(log: RebalanceLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "period_yyyymm": log.period_yyyymm,
        "triggered_by": log.triggered_by,
        "started_at": log.started_at.isoformat(),
        "finished_at": log.finished_at.isoformat(),
        "T_before": log.T_before,
        "T_after": log.T_after,
        "scanned": log.scanned,
        "changed": log.changed,
        "algorithm_version": log.algorithm_version,
    }
