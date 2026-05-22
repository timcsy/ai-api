"""Admin endpoints for the adaptive quota pool (Phase 3c)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.config import get_settings
from ai_api.models import (
    Allocation,
    AllocationStatus,
    RebalanceLog,
)
from ai_api.services.quota_pool import (
    PoolDisabledError,
    PoolExhaustedByReservedError,
    PoolIdleError,
    RebalanceConservationError,
    apply_rebalance,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


@router.get("/quota-pool/status")
async def get_pool_status(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    settings = get_settings()
    T = settings.pool_total_tokens_per_month
    floor = settings.pool_floor_per_allocation

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

    return {
        "total_T": T,
        "reserved": {"service": service_reserved, "locked": locked_reserved},
        "distributable": T - service_reserved - locked_reserved,
        "pool_member_count": pool_count,
        "floor": floor,
        "settings": {"enabled": T > 0},
        "last_rebalance_at": last_at.isoformat() if last_at else None,
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
