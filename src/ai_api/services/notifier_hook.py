"""Phase 13: notifier subscription glue.

Connects `audit.record()` (the single emit point for audit events) to the
notifier channel. Fire-and-forget via `asyncio.create_task` — the audit write
itself MUST NOT fail because of a notifier error (FR-025), and the request
handler MUST NOT block waiting for SMTP.

Test helpers:
  `drain_notifier_tasks()` — await all currently-pending tasks; integration
  tests call this after triggering an event so they can synchronously assert
  the resulting notification_record / aiosmtpd state.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType
from ai_api.services.notifier import NotificationEvent
from ai_api.services.notifier_email import EmailNotifier

logger = logging.getLogger(__name__)

# Default v1 set — operator can override via env NOTIFY_EVENT_TYPES_OVERRIDE
DEFAULT_NOTIFY_EVENT_TYPES: frozenset[str] = frozenset({
    AuditEventType.allocation_quarantined.value,
    AuditEventType.responses_upstream_error_burst.value,
    AuditEventType.provider_credential_auth_failed.value,
})


def _effective_event_types() -> frozenset[str]:
    override = get_settings().notify_event_types_override
    if override:
        return frozenset(override)
    return DEFAULT_NOTIFY_EVENT_TYPES


# Module-level pending task set so tests can drain them; in production
# each task self-discards on completion.
_pending_tasks: set[asyncio.Task[Any]] = set()


async def _safe_notify(event: NotificationEvent) -> None:
    """Per-event dispatch. Always opens a fresh session — caller's request
    session is closed by the time we run."""
    sm = get_sessionmaker()
    try:
        async with sm() as session:
            notifier = EmailNotifier()
            await notifier.notify(session, event)
            await session.commit()
    except BaseException:
        logger.exception(
            "notifier task failed event_type=%s target_id=%s",
            event.event_type, event.target_id,
        )


def fire(event: NotificationEvent) -> None:
    """Dispatch event to the notifier as a fire-and-forget task.

    No-op if `event.event_type` is not in the active subscription set.
    """
    if event.event_type not in _effective_event_types():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (e.g. some sync test contexts); drop silently —
        # the audit write itself succeeds.
        logger.debug(
            "notifier hook skipped: no running event loop (event_type=%s)",
            event.event_type,
        )
        return
    task = loop.create_task(_safe_notify(event))
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def drain_notifier_tasks() -> None:
    """Test helper: await all currently-pending notifier tasks.

    Tests should call this after `audit.record(...)` and before asserting
    notification_record / SMTP server state.
    """
    while _pending_tasks:
        # Snapshot current set; new tasks may be spawned during await
        current = list(_pending_tasks)
        await asyncio.gather(*current, return_exceptions=True)
