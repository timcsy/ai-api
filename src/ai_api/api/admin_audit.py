"""Phase 5+: admin audit log viewer endpoint."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.models import ActorType, AuditEventType, AuthAuditLog

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("/audit")
async def list_audit(
    actor_type: ActorType | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    event_type: AuditEventType | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None, description="ISO 8601 inclusive lower bound"),
    until: datetime | None = Query(default=None, description="ISO 8601 exclusive upper bound"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    stmt = select(AuthAuditLog).order_by(desc(AuthAuditLog.created_at))
    if actor_type is not None:
        stmt = stmt.where(AuthAuditLog.actor_type == actor_type)
    if actor_id is not None:
        stmt = stmt.where(AuthAuditLog.actor_id == actor_id)
    if event_type is not None:
        stmt = stmt.where(AuthAuditLog.event_type == event_type)
    if target_type is not None:
        stmt = stmt.where(AuthAuditLog.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(AuthAuditLog.target_id == target_id)
    if since is not None:
        stmt = stmt.where(AuthAuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuthAuditLog.created_at < until)
    rows = list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return {
        "limit": limit,
        "offset": offset,
        "rows": [
            {
                "id": r.id,
                "event_type": r.event_type.value,
                "actor_type": r.actor_type.value,
                "actor_id": r.actor_id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "source_ip": r.source_ip,
                "request_id": r.request_id,
                "created_at": r.created_at.isoformat(),
                "details": r.details,
                "redacted_message": r.redacted_message,
            }
            for r in rows
        ],
    }


@router.get("/audit/event-types")
async def list_event_types() -> list[str]:
    """Vocabulary endpoint for the audit filter UI."""
    return sorted(e.value for e in AuditEventType)
