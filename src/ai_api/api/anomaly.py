"""Admin endpoints for the anomaly-detector config (spec 054).

GET/PUT the auto-quarantine switch, an optional pause-until (auto-resumes when it
passes), and the detection thresholds — so admins can pause enforcement during a
workshop and tune sensitivity without a redeploy. Single source of truth in DB
(env is bootstrap default only); un-quarantine itself lives in api/allocations.py.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.auth import audit
from ai_api.models import ActorType, AuditEventType
from ai_api.services.anomaly import get_anomaly_config

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


class AnomalyConfigUpdate(BaseModel):
    auto_quarantine_enabled: bool | None = None
    pause_until: datetime | None = None
    clear_pause: bool = False  # explicitly clear pause_until (since null is ambiguous)
    threshold_multiplier: float | None = Field(default=None, ge=1)
    min_calls: int | None = Field(default=None, ge=0)
    absolute_cold_start: int | None = Field(default=None, ge=0)
    baseline_min_calls: int | None = Field(default=None, ge=0)


def _serialize(cfg: Any, now: datetime) -> dict[str, Any]:
    return {
        "auto_quarantine_enabled": cfg.auto_quarantine_enabled,
        "pause_until": cfg.pause_until.isoformat() if cfg.pause_until else None,
        "effective_enforcing": cfg.effective_enforcing(now),
        "status": cfg.status(now),
        "thresholds": {
            "threshold_multiplier": cfg.threshold_multiplier,
            "min_calls": cfg.min_calls,
            "absolute_cold_start": cfg.absolute_cold_start,
            "baseline_min_calls": cfg.baseline_min_calls,
        },
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        "updated_by": cfg.updated_by,
    }


@router.get("/anomaly/config")
async def get_config(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    cfg = await get_anomaly_config(session)
    return _serialize(cfg, datetime.now(UTC))


@router.put("/anomaly/config")
async def update_config(
    body: AnomalyConfigUpdate = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Partial update: only provided fields change. Pydantic enforces the numeric
    bounds (multiplier >= 1, others >= 0) → 422 on violation."""
    cfg = await get_anomaly_config(session)
    changed: dict[str, Any] = {}

    if body.auto_quarantine_enabled is not None:
        cfg.auto_quarantine_enabled = body.auto_quarantine_enabled
        changed["auto_quarantine_enabled"] = body.auto_quarantine_enabled
    if body.clear_pause:
        cfg.pause_until = None
        changed["pause_until"] = None
    elif body.pause_until is not None:
        if body.pause_until.tzinfo is None:
            body.pause_until = body.pause_until.replace(tzinfo=UTC)
        cfg.pause_until = body.pause_until
        changed["pause_until"] = body.pause_until.isoformat()
    for attr in ("threshold_multiplier", "min_calls", "absolute_cold_start", "baseline_min_calls"):
        val = getattr(body, attr)
        if val is not None:
            setattr(cfg, attr, val)
            changed[attr] = val

    if not changed:
        raise HTTPException(
            status_code=422, detail=_err("invalid_anomaly_config", "no fields to update")
        )

    now = datetime.now(UTC)
    cfg.updated_at = now
    cfg.updated_by = "admin"
    await audit.record(
        session,
        event_type=AuditEventType.anomaly_config_updated,
        actor_type=ActorType.admin,
        target_type="anomaly_config",
        target_id="1",
        details=changed,
    )
    await session.commit()
    return _serialize(cfg, now)
