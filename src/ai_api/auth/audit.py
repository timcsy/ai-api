"""Auth audit log: structured event recording with redaction."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import ActorType, AuditEventType, AuthAuditLog
from ai_api.observability.logging import redact_string


async def record(
    db: AsyncSession,
    *,
    event_type: AuditEventType,
    actor_type: ActorType,
    actor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
    message: str | None = None,
) -> AuthAuditLog:
    entry = AuthAuditLog(
        id=str(ULID()),
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        source_ip=source_ip,
        user_agent=(user_agent or "")[:512] or None,
        request_id=request_id,
        created_at=datetime.now(UTC),
        details=_redact_details(details) if details else None,
        redacted_message=redact_string(message) if message else None,
    )
    db.add(entry)
    await db.flush()

    # Phase 13: notifier hook — fire-and-forget. MUST NOT impact this write
    # path (FR-025). See services/notifier_hook.py.
    try:
        from ai_api.services.notifier import NotificationEvent
        from ai_api.services.notifier_hook import fire as _fire_notifier

        _fire_notifier(
            NotificationEvent(
                event_type=event_type.value,
                occurred_at=entry.created_at,
                audit_event_id=entry.id,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )
    except Exception:
        import logging
        logging.getLogger(__name__).debug("notifier hook wiring failed", exc_info=True)
    return entry


def _redact_details(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k] = redact_string(v)
        else:
            out[k] = v
    return out
