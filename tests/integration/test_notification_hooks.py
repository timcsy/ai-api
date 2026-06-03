"""Phase 13 US2 T029-T033: integration tests for audit -> notifier hook."""
from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import Message
from typing import Any
from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest
import pytest_asyncio
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message as AiosmtpdMessageHandler
from aiosmtpd.smtp import AuthResult
from sqlalchemy import select

from ai_api.auth import audit
from ai_api.config import get_settings
from ai_api.db import Base, dispose_engine, get_engine, get_sessionmaker, reset_engine_for_testing
from ai_api.models import (
    ActorType,
    AuditEventType,
    AuthAuditLog,
    NotificationConfig,
    NotificationConfigStatus,
    NotificationOutcome,
    NotificationRecord,
)
from ai_api.services.notifier_hook import drain_notifier_tasks


def _permissive_authenticator(
    server: Any, session: Any, envelope: Any, mechanism: str, auth_data: Any
) -> AuthResult:
    """Accept any credentials in tests — we only verify routing/delivery, not auth."""
    return AuthResult(success=True)


class CapturingHandler(AiosmtpdMessageHandler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[Message] = []

    def handle_message(self, message: Message) -> None:
        self.messages.append(message)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture
async def smtp_server() -> Any:
    handler = CapturingHandler()
    port = _free_port()
    controller = Controller(
        handler,
        hostname="127.0.0.1",
        port=port,
        authenticator=_permissive_authenticator,
        # auth_require_tls=False allows AUTH over plaintext (test-only convenience)
        auth_require_tls=False,
    )
    controller.start()
    try:
        yield controller, handler
    finally:
        controller.stop()
        await asyncio.sleep(0)


@pytest_asyncio.fixture
async def fresh_db() -> Any:
    """Per-test fresh in-memory SQLite engine + tables."""
    get_settings.cache_clear()
    reset_engine_for_testing("sqlite+aiosqlite:///:memory:")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


async def _save_config(
    *, smtp_host: str, smtp_port: int, recipients: list[str], password: str = "x"
) -> None:
    from ai_api.services.notifications import NotificationConfigService

    sm = get_sessionmaker()
    async with sm() as session:
        await NotificationConfigService(session).save(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username="bot@example.com",
            smtp_password=password,
            sender_email="bot@example.com",
            sender_name="AI API Test",
            recipients=recipients,
        )
        await session.commit()


async def _fire_quarantine(*, target_id: str = "alloc_abc12345") -> AuthAuditLog:
    sm = get_sessionmaker()
    async with sm() as session:
        entry = await audit.record(
            session,
            event_type=AuditEventType.allocation_quarantined,
            actor_type=ActorType.system,
            target_type="allocation",
            target_id=target_id,
            details={
                "trigger": "anomaly_detector",
                "last_hour_calls": 1100,
                "baseline_per_hour": 100.0,
                "reason": "ratio",
            },
        )
        await session.commit()
        return entry


async def _list_records() -> list[NotificationRecord]:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = (
            await session.execute(select(NotificationRecord).order_by(NotificationRecord.created_at))
        ).scalars().all()
        return list(rows)


# ----- T029 -----

@pytest.mark.asyncio
async def test_allocation_quarantined_event_sends_email(
    fresh_db: Any, smtp_server: Any
) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname,
        smtp_port=controller.port,
        recipients=["admin@example.com", "ops@example.com"],
    )
    await _fire_quarantine(target_id="alloc_abc12345")
    await drain_notifier_tasks()

    # Both recipients addressed in a single message
    assert len(handler.messages) == 1, f"expected 1 msg, got {len(handler.messages)}"
    msg = handler.messages[0]
    assert "admin@example.com" in msg["To"]
    assert "ops@example.com" in msg["To"]
    subject_text = str(make_header(decode_header(msg["Subject"])))
    assert "分配自動隔離" in subject_text
    assert subject_text.endswith("alloc_ab")  # first 8 chars of target_id (per template)
    body_part = msg.get_payload(decode=True)
    body = body_part.decode("utf-8") if isinstance(body_part, bytes) else str(msg.get_payload())
    assert "1100" in body, body
    assert "baseline" in body.lower() or "基準" in body or "100" in body
    assert "/admin/" in body  # link present

    records = await _list_records()
    sent_records = [r for r in records if r.outcome == NotificationOutcome.sent]
    assert len(sent_records) == 1
    rec = sent_records[0]
    assert rec.event_type == AuditEventType.allocation_quarantined.value
    assert set(rec.recipients) == {"admin@example.com", "ops@example.com"}
    assert rec.audit_event_id is not None
    assert rec.latency_ms is not None and rec.latency_ms < 30_000


# ----- T030 -----

@pytest.mark.asyncio
async def test_quarantine_event_when_smtp_unset_skips_silently(fresh_db: Any) -> None:
    # No config saved
    entry = await _fire_quarantine()
    await drain_notifier_tasks()

    # audit row was written
    sm = get_sessionmaker()
    async with sm() as session:
        audit_row = (
            await session.execute(select(AuthAuditLog).where(AuthAuditLog.id == entry.id))
        ).scalar_one_or_none()
        assert audit_row is not None

    records = await _list_records()
    assert len(records) == 1
    assert records[0].outcome == NotificationOutcome.skipped_disabled


# ----- T031 -----

@pytest.mark.asyncio
async def test_one_recipient_failure_does_not_block_others(fresh_db: Any) -> None:
    await _save_config(
        smtp_host="dummy.invalid", smtp_port=587,
        recipients=["good@example.com", "bad@example.com"],
    )

    # Mock _smtp_send to return errors dict with one rejected recipient
    from ai_api.services import notifier_email
    fake_errors = {"bad@example.com": (550, b"mailbox unavailable")}
    with patch.object(
        notifier_email, "_smtp_send", new=AsyncMock(return_value=(fake_errors, "OK"))
    ):
        await _fire_quarantine()
        await drain_notifier_tasks()

    records = await _list_records()
    sent = [r for r in records if r.outcome == NotificationOutcome.sent]
    assert len(sent) == 1, f"expected one 'sent' record, got {[r.outcome for r in records]}"
    rec = sent[0]
    assert rec.per_recipient_status["good@example.com"] == "ok"
    assert "550" in rec.per_recipient_status["bad@example.com"]
    assert "mailbox unavailable" in rec.per_recipient_status["bad@example.com"]


# ----- T032 -----

@pytest.mark.asyncio
async def test_credentials_invalid_status_blocks_send(fresh_db: Any) -> None:
    await _save_config(
        smtp_host="dummy", smtp_port=587, recipients=["admin@example.com"]
    )
    # Force status to credentials_invalid
    sm = get_sessionmaker()
    async with sm() as session:
        cfg = (await session.execute(select(NotificationConfig))).scalar_one()
        cfg.status = NotificationConfigStatus.credentials_invalid
        await session.commit()

    # Patch _smtp_send so any accidental send call would fail loudly
    from ai_api.services import notifier_email
    with patch.object(
        notifier_email, "_smtp_send",
        new=AsyncMock(side_effect=AssertionError("must NOT be called")),
    ):
        await _fire_quarantine()
        await drain_notifier_tasks()

    records = await _list_records()
    assert len(records) == 1
    assert records[0].outcome == NotificationOutcome.skipped_disabled
    assert "credentials_invalid" in (records[0].error_message or "")


# ----- T033 -----

@pytest.mark.asyncio
async def test_email_send_failure_does_not_break_audit(fresh_db: Any) -> None:
    await _save_config(
        smtp_host="dummy", smtp_port=587, recipients=["admin@example.com"]
    )
    from ai_api.services import notifier_email
    with patch.object(
        notifier_email, "_smtp_send",
        new=AsyncMock(side_effect=aiosmtplib.SMTPConnectError("connection refused")),
    ):
        entry = await _fire_quarantine()
        await drain_notifier_tasks()

    # audit row exists despite notifier failure
    sm = get_sessionmaker()
    async with sm() as session:
        audit_row = (
            await session.execute(select(AuthAuditLog).where(AuthAuditLog.id == entry.id))
        ).scalar_one_or_none()
        assert audit_row is not None

    records = await _list_records()
    assert len(records) == 1
    assert records[0].outcome == NotificationOutcome.send_failed_connect
    assert "connection refused" in (records[0].error_message or "")


# ===== Phase 5 (US3): other event types =====

async def _add_upstream_error_calls(count: int) -> None:
    """Seed `count` CallRecord rows with outcome=upstream_error within the window."""
    from datetime import timedelta

    from ulid import ULID

    from ai_api.models import CallOutcome, CallRecord

    sm = get_sessionmaker()
    base = datetime.now(UTC)
    async with sm() as session:
        for i in range(count):
            ts = base - timedelta(seconds=i * 2)
            session.add(
                CallRecord(
                    id=str(ULID()),
                    request_id=f"r-{ULID()}",
                    allocation_id=None,
                    subject="x@y.com",
                    model="azure/gpt-5.4",
                    started_at=ts,
                    finished_at=ts,
                    status_code=502,
                    outcome=CallOutcome.upstream_error,
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                )
            )
        await session.commit()


# ----- T040 -----

@pytest.mark.asyncio
async def test_upstream_error_burst_triggers_notification(
    fresh_db: Any, smtp_server: Any
) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname,
        smtp_port=controller.port,
        recipients=["admin@example.com"],
    )
    # 10 upstream errors within the 5-min window crosses default threshold.
    await _add_upstream_error_calls(10)

    from ai_api.services.upstream_burst_detector import detect_upstream_burst

    sm = get_sessionmaker()
    async with sm() as session:
        decision = await detect_upstream_burst(session)
        await session.commit()
    assert decision is not None
    assert decision.failure_count == 10
    await drain_notifier_tasks()

    assert len(handler.messages) == 1
    subject_text = str(make_header(decode_header(handler.messages[0]["Subject"])))
    assert "上游連續失敗" in subject_text
    body_part = handler.messages[0].get_payload(decode=True)
    body = body_part.decode("utf-8") if isinstance(body_part, bytes) else ""
    assert "10" in body
    assert "azure/gpt-5.4" in body

    records = await _list_records()
    sent = [r for r in records if r.outcome == NotificationOutcome.sent]
    assert len(sent) == 1
    assert sent[0].event_type == "responses_upstream_error_burst"


@pytest.mark.asyncio
async def test_upstream_burst_below_threshold_does_not_fire(fresh_db: Any) -> None:
    await _add_upstream_error_calls(5)  # below threshold 10
    from ai_api.services.upstream_burst_detector import detect_upstream_burst

    sm = get_sessionmaker()
    async with sm() as session:
        decision = await detect_upstream_burst(session)
        await session.commit()
    assert decision is None


# ----- T041 -----

@pytest.mark.asyncio
async def test_provider_credential_auth_failed_triggers_notification(
    fresh_db: Any, smtp_server: Any
) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname,
        smtp_port=controller.port,
        recipients=["admin@example.com"],
    )
    sm = get_sessionmaker()
    async with sm() as session:
        await audit.record(
            session,
            event_type=AuditEventType.provider_credential_auth_failed,
            actor_type=ActorType.system,
            target_type="provider_credential",
            target_id="cred_abc123",
            details={"provider": "azure"},
        )
        await session.commit()
    await drain_notifier_tasks()

    assert len(handler.messages) == 1
    subject_text = str(make_header(decode_header(handler.messages[0]["Subject"])))
    assert "憑證失效" in subject_text
    body_part = handler.messages[0].get_payload(decode=True)
    body = body_part.decode("utf-8") if isinstance(body_part, bytes) else ""
    assert "azure" in body


# ----- T042 -----

@pytest.mark.asyncio
async def test_daily_cap_exceeded_event_template_renders(
    fresh_db: Any, smtp_server: Any
) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname,
        smtp_port=controller.port,
        recipients=["admin@example.com"],
    )
    sm = get_sessionmaker()
    async with sm() as session:
        await audit.record(
            session,
            event_type=AuditEventType.allocation_daily_cap_exceeded,
            actor_type=ActorType.system,
            target_type="allocation",
            target_id="alloc_daily99",
            details={"daily_token_cap": 50000, "today_tokens": 50120},
        )
        await session.commit()
    await drain_notifier_tasks()

    assert len(handler.messages) == 1
    subject_text = str(make_header(decode_header(handler.messages[0]["Subject"])))
    assert "每日上限" in subject_text
    body_part = handler.messages[0].get_payload(decode=True)
    body = body_part.decode("utf-8") if isinstance(body_part, bytes) else ""
    assert "50000" in body
    assert "50120" in body


@pytest.fixture(autouse=True)
def _setup_test_env() -> Any:
    """Make sure timestamps for the rendered email use today's date."""
    yield datetime.now(UTC)
