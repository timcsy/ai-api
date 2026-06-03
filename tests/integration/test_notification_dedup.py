"""Phase 13 US4 T049-T052: 5-minute same-event-type deduplication."""
from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime, timedelta
from email.message import Message
from typing import Any

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
    NotificationDedupBucket,
    NotificationOutcome,
    NotificationRecord,
)
from ai_api.services.notifier_hook import drain_notifier_tasks


class CapturingHandler(AiosmtpdMessageHandler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[Message] = []

    def handle_message(self, message: Message) -> None:
        self.messages.append(message)


def _permissive_authenticator(
    server: Any, session: Any, envelope: Any, mechanism: str, auth_data: Any
) -> AuthResult:
    return AuthResult(success=True)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture
async def smtp_server() -> Any:
    handler = CapturingHandler()
    controller = Controller(
        handler, hostname="127.0.0.1", port=_free_port(),
        authenticator=_permissive_authenticator, auth_require_tls=False,
    )
    controller.start()
    try:
        yield controller, handler
    finally:
        controller.stop()
        await asyncio.sleep(0)


@pytest_asyncio.fixture
async def fresh_db() -> Any:
    get_settings.cache_clear()
    reset_engine_for_testing("sqlite+aiosqlite:///:memory:")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


async def _save_config(*, smtp_host: str, smtp_port: int, recipients: list[str]) -> None:
    from ai_api.services.notifications import NotificationConfigService

    sm = get_sessionmaker()
    async with sm() as session:
        await NotificationConfigService(session).save(
            smtp_host=smtp_host, smtp_port=smtp_port, smtp_username="bot@example.com",
            smtp_password="pw", sender_email="bot@example.com", sender_name="Test",
            recipients=recipients,
        )
        await session.commit()


async def _fire_event(event_type: AuditEventType, target_id: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await audit.record(
            session, event_type=event_type, actor_type=ActorType.system,
            target_type="allocation", target_id=target_id,
            details={"last_hour_calls": 1100, "baseline_per_hour": 100.0, "reason": "ratio"},
        )
        await session.commit()
    await drain_notifier_tasks()


async def _records() -> list[NotificationRecord]:
    sm = get_sessionmaker()
    async with sm() as session:
        return list(
            (await session.execute(select(NotificationRecord).order_by(NotificationRecord.created_at)))
            .scalars().all()
        )


async def _buckets() -> list[NotificationDedupBucket]:
    sm = get_sessionmaker()
    async with sm() as session:
        return list((await session.execute(select(NotificationDedupBucket))).scalars().all())


# ----- T049 -----

@pytest.mark.asyncio
async def test_burst_within_5min_window_sends_once(fresh_db: Any, smtp_server: Any) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname, smtp_port=controller.port,
        recipients=["admin@example.com"],
    )
    # 50 events, same type, well within 5 min.
    for i in range(50):
        await _fire_event(AuditEventType.allocation_quarantined, f"alloc_{i}")

    # Exactly one email sent.
    assert len(handler.messages) == 1, f"expected 1 email, got {len(handler.messages)}"

    buckets = await _buckets()
    assert len(buckets) == 1
    assert buckets[0].event_count == 50

    records = await _records()
    sent = [r for r in records if r.outcome == NotificationOutcome.sent]
    suppressed = [r for r in records if r.outcome == NotificationOutcome.suppressed]
    assert len(sent) == 1
    assert len(suppressed) == 49
    # all suppressed point at the same bucket; the bucket's primary is the sent one
    assert all(r.dedup_bucket_id == buckets[0].id for r in suppressed)
    assert buckets[0].primary_record_id == sent[0].id


# ----- T050 -----

@pytest.mark.asyncio
async def test_different_event_types_send_separately(fresh_db: Any, smtp_server: Any) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname, smtp_port=controller.port,
        recipients=["admin@example.com"],
    )
    await _fire_event(AuditEventType.allocation_quarantined, "alloc_a")
    await _fire_event(AuditEventType.provider_credential_auth_failed, "cred_b")

    # Two emails — dedup is per event type.
    assert len(handler.messages) == 2
    buckets = await _buckets()
    assert len(buckets) == 2


# ----- T051 -----

@pytest.mark.asyncio
async def test_window_expires_starts_new_bucket(fresh_db: Any, smtp_server: Any) -> None:
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname, smtp_port=controller.port,
        recipients=["admin@example.com"],
    )
    await _fire_event(AuditEventType.allocation_quarantined, "alloc_a")
    assert len(handler.messages) == 1

    # Manually expire the bucket (simulate >5 min passing).
    sm = get_sessionmaker()
    async with sm() as session:
        bucket = (await session.execute(select(NotificationDedupBucket))).scalar_one()
        bucket.window_end = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    await _fire_event(AuditEventType.allocation_quarantined, "alloc_b")
    # Second email sent because the window expired.
    assert len(handler.messages) == 2
    buckets = await _buckets()
    assert len(buckets) == 2


# ----- T052 -----

@pytest.mark.asyncio
async def test_sequential_same_type_events_dedup_to_one(
    fresh_db: Any, smtp_server: Any
) -> None:
    """Sequential events (the realistic per-request case — audit.record commits
    before the next, then fires the notifier) dedup to a single email.

    NOTE: truly-simultaneous events across replicas may each send (bounded by
    replica count) — this is the accepted design limit (research R3); SQLite
    in-memory cannot model cross-connection row locks, so we assert the
    realistic sequential guarantee here.
    """
    controller, handler = smtp_server
    await _save_config(
        smtp_host=controller.hostname, smtp_port=controller.port,
        recipients=["admin@example.com"],
    )

    # Fire 5 same-type events; each fully completes (audit + notify drain) before
    # the next starts — exactly how a single gateway process serialises requests.
    for i in range(5):
        await _fire_event(AuditEventType.allocation_quarantined, f"alloc_{i}")

    assert len(handler.messages) == 1, f"expected 1 email, got {len(handler.messages)}"
    buckets = await _buckets()
    assert len(buckets) == 1
    assert buckets[0].event_count == 5
