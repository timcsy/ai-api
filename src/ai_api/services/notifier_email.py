"""Phase 13: EmailNotifier — SMTP-based admin notification dispatch.

Implementation contract: specs/022-admin-email-notifications/contracts/notifier-interface.md
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import (
    NotificationConfig,
    NotificationConfigStatus,
    NotificationOutcome,
    NotificationRecord,
)
from ai_api.services.crypto import decrypt_str
from ai_api.services.notifier import (
    NotificationEvent,
    NotificationResult,
    Notifier,
)

logger = logging.getLogger(__name__)

# Connect-phase timeout: must reach SMTP server within this many seconds.
_CONNECT_TIMEOUT_S = 15
# Per-command timeout: total send op should finish within FR-017 budget (30s).
_COMMAND_TIMEOUT_S = 30


def classify_smtp_exception(
    exc: BaseException, *, mode: str
) -> tuple[NotificationOutcome, int | None]:
    """Map an exception raised during SMTP send to a notification outcome.

    `mode` is "send" for real event notifications, "test" for test-send button.
    """
    is_test = mode == "test"
    if isinstance(exc, aiosmtplib.SMTPAuthenticationError):
        out = NotificationOutcome.test_failed_auth if is_test else NotificationOutcome.send_failed_auth
        return out, exc.code
    if isinstance(exc, aiosmtplib.SMTPSenderRefused):
        out = NotificationOutcome.test_failed_sender if is_test else NotificationOutcome.send_failed_sender
        return out, exc.code
    if isinstance(exc, aiosmtplib.SMTPRecipientsRefused):
        out = (
            NotificationOutcome.test_failed_recipient if is_test
            else NotificationOutcome.send_failed_all_recipients
        )
        return out, None
    if isinstance(exc, (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected, OSError)):
        code = getattr(exc, "code", None)
        out = NotificationOutcome.test_failed_connect if is_test else NotificationOutcome.send_failed_connect
        return out, code if isinstance(code, int) else None
    out = NotificationOutcome.test_failed_unknown if is_test else NotificationOutcome.send_failed_unknown
    return out, None


def _mask_email(addr: str) -> str:
    """`tim@school.edu.tw` -> `tim***@school.edu.tw`"""
    if "@" not in addr:
        return "***"
    local, _, domain = addr.partition("@")
    keep = local[:3] if len(local) > 3 else local[:1]
    return f"{keep}***@{domain}"


async def _smtp_send(
    *,
    message: EmailMessage,
    hostname: str,
    port: int,
    username: str | None,
    password: str | None,
) -> tuple[dict[str, tuple[int, bytes]], str]:
    """Thin wrapper around aiosmtplib.send so tests can patch a single seam.

    Returns aiosmtplib's native `(per_recipient_errors, response_message)`. An
    empty errors dict indicates success; a non-empty dict maps each rejected
    recipient to its SMTP `(code, message_bytes)`.

    TLS policy: port 465 -> direct TLS; otherwise STARTTLS (auto-detected by
    aiosmtplib if the server advertises it).
    """
    use_tls = port == 465
    start_tls: bool | None = None if use_tls else True
    return await aiosmtplib.send(
        message,
        hostname=hostname,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        start_tls=start_tls,
        timeout=_COMMAND_TIMEOUT_S,
    )


def _build_message(
    *, sender_email: str, sender_name: str, recipients: list[str], subject: str, body: str
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _build_test_message(
    *, sender_email: str, sender_name: str, recipient: str
) -> tuple[str, str, EmailMessage]:
    subject = "[AI API] 測試通知"
    body = (
        "管理員您好，\n\n"
        "這是 AI API Manager 的測試信，用以確認 SMTP 設定可用。\n"
        "如果您收到此信，代表本平台已可在重要事件發生時寄信通知您。\n\n"
        "— AI API Manager\n"
    )
    msg = _build_message(
        sender_email=sender_email,
        sender_name=sender_name,
        recipients=[recipient],
        subject=subject,
        body=body,
    )
    return subject, body, msg


class EmailNotifier(Notifier):
    """SMTP-backed admin notification channel."""

    async def notify(
        self,
        session: AsyncSession,
        event: NotificationEvent,
    ) -> NotificationResult:
        # Implemented in US2/US4 — placeholder for now (US1 only delivers test_send).
        raise NotImplementedError("EmailNotifier.notify is delivered in US2/US4")

    async def test_send(
        self,
        session: AsyncSession,
        test_recipient: str,
    ) -> NotificationResult:
        """Send a one-off test email to verify the configured channel.

        FR-007: uses test_recipient ONLY; the saved recipient list is NOT consulted.
        """
        start = time.monotonic()
        # Read config
        config = (
            await session.execute(select(NotificationConfig).limit(1))
        ).scalar_one_or_none()
        if config is None:
            raise ValueError("notification config not set")

        # Decrypt password — credentials_invalid status if key mismatch
        try:
            password = decrypt_str(config.smtp_password_encrypted)
        except Exception as exc:
            # Mark config as credentials_invalid so admin sees the right UI state
            config.status = NotificationConfigStatus.credentials_invalid
            await session.flush()
            return _persist_and_return_result(
                session=session,
                event_type="test_send",
                outcome=NotificationOutcome.test_failed_unknown,
                recipients=[test_recipient],
                subject="[AI API] 測試通知",
                body_preview="(decryption failed)",
                per_recipient_status={test_recipient: f"decrypt failed: {exc}"},
                smtp_response_code=None,
                error_message=f"stored password could not be decrypted: {exc}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        subject, body, msg = _build_test_message(
            sender_email=config.sender_email,
            sender_name=config.sender_name,
            recipient=test_recipient,
        )

        outcome: NotificationOutcome
        smtp_code: int | None = None
        per_recipient: dict[str, str] = {}
        error_message: str | None = None
        try:
            errors, response = await _smtp_send(
                message=msg,
                hostname=config.smtp_host,
                port=config.smtp_port,
                username=config.smtp_username,
                password=password,
            )
            if errors:
                per_recipient = {
                    addr: f"{err_code}: {err_msg.decode(errors='replace') if isinstance(err_msg, bytes) else err_msg}"
                    for addr, (err_code, err_msg) in errors.items()
                }
                first_code = next(iter(errors.values()))[0] if errors else None
                smtp_code = int(first_code) if isinstance(first_code, int) else None
                outcome = NotificationOutcome.test_failed_recipient
                error_message = f"recipient rejected: {per_recipient}"
            else:
                outcome = NotificationOutcome.test_sent
                per_recipient = {test_recipient: "ok"}
                # aiosmtplib returns a brief status string; SMTP 250 = success.
                smtp_code = 250 if response else None
        except BaseException as exc:
            outcome, smtp_code = classify_smtp_exception(exc, mode="test")
            per_recipient = {test_recipient: f"{outcome.value}: {exc}"[:200]}
            error_message = str(exc)[:500]
            logger.exception(
                "test_send failed mode=%s outcome=%s recipient=%s",
                "test", outcome.value, _mask_email(test_recipient),
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        # Update config status on successful test
        if outcome == NotificationOutcome.test_sent:
            config.status = NotificationConfigStatus.verified
        elif outcome == NotificationOutcome.test_failed_auth:
            config.status = NotificationConfigStatus.credentials_invalid
        config.last_test_at = datetime.now(UTC)
        config.last_test_outcome = outcome.value
        config.last_test_error = error_message
        await session.flush()

        return _persist_and_return_result(
            session=session,
            event_type="test_send",
            outcome=outcome,
            recipients=[test_recipient],
            subject=subject,
            body_preview=body[:500],
            per_recipient_status=per_recipient,
            smtp_response_code=smtp_code,
            error_message=error_message,
            latency_ms=latency_ms,
        )


def _persist_and_return_result(
    *,
    session: AsyncSession,
    event_type: str,
    outcome: NotificationOutcome,
    recipients: list[str],
    subject: str,
    body_preview: str,
    per_recipient_status: dict[str, str],
    smtp_response_code: int | None,
    error_message: str | None,
    latency_ms: int,
) -> NotificationResult:
    record = NotificationRecord(
        id=str(ULID()),
        event_type=event_type,
        audit_event_id=None,
        dedup_bucket_id=None,
        outcome=outcome,
        recipients=recipients,
        per_recipient_status=per_recipient_status,
        subject=subject[:256],
        body_preview=body_preview[:500],
        smtp_response_code=smtp_response_code,
        error_message=error_message[:5000] if error_message else None,
        latency_ms=latency_ms,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    logger.info(
        "notification_record event_type=%s outcome=%s recipients_count=%d latency_ms=%d "
        "smtp_code=%s recipients_masked=%s",
        event_type,
        outcome.value,
        len(recipients),
        latency_ms,
        smtp_response_code,
        [_mask_email(r) for r in recipients],
    )
    return NotificationResult(
        outcome=outcome,
        latency_ms=latency_ms,
        smtp_response_code=smtp_response_code,
        per_recipient_status=per_recipient_status,
        error_message=error_message,
        recipients=recipients,
    )


# Re-export NotificationEvent/Result for callers that prefer importing from
# the email-specific module (matches existing pattern in other services).
__all__ = [
    "EmailNotifier",
    "NotificationEvent",
    "NotificationResult",
    "classify_smtp_exception",
]
