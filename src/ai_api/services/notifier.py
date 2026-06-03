"""Phase 13: Notifier abstraction.

Single-channel dispatch interface. v1 implementation: EmailNotifier (SMTP via
aiosmtplib). Future channels (LINE Bot, Web Push) are parallel adapters that
implement the same ABC without touching existing callers.

Contracts: see specs/022-admin-email-notifications/contracts/notifier-interface.md
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import NotificationOutcome


@dataclass(frozen=True)
class NotificationEvent:
    """Standardised envelope for events that may trigger a notification."""

    event_type: str  # AuditEventType value
    occurred_at: datetime  # tz-aware UTC
    audit_event_id: str | None = None  # None for test sends
    target_type: str | None = None  # e.g. "allocation"
    target_id: str | None = None
    target_display_name: str | None = None  # friendly name when available
    details: dict[str, Any] | None = None  # event-specific data


@dataclass(frozen=True)
class NotificationResult:
    """Outcome of a single dispatch attempt."""

    outcome: NotificationOutcome
    latency_ms: int
    smtp_response_code: int | None = None
    per_recipient_status: dict[str, str] | None = None
    error_message: str | None = None
    recipients: list[str] | None = None  # actual recipients targeted (may differ from config)


class Notifier(ABC):
    """A single notification channel."""

    @abstractmethod
    async def notify(
        self,
        session: AsyncSession,
        event: NotificationEvent,
    ) -> NotificationResult:
        """Dispatch event to the channel.

        MUST:
          - Read NotificationConfig; absent/disabled -> skipped_disabled
          - Apply 5-min same-event-type dedup via notification_dedup_bucket
          - Persist a notification_record row regardless of outcome
          - Never raise; capture exceptions and return them via NotificationResult
          - Complete within 30 seconds (FR-017)
        """

    @abstractmethod
    async def test_send(
        self,
        session: AsyncSession,
        test_recipient: str,
    ) -> NotificationResult:
        """Send a synthetic test email to a one-off recipient.

        Does NOT consult the saved recipient list (FR-007 — chosen option A).
        Does NOT consult or update dedup buckets.
        Persists a notification_record row with outcome=test_sent / test_failed_*.
        """
