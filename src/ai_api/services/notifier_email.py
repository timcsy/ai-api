"""Phase 13: EmailNotifier — SMTP-based admin notification dispatch.

Implementation contract: specs/022-admin-email-notifications/contracts/notifier-interface.md
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import (
    NotificationConfig,
    NotificationConfigStatus,
    NotificationDedupBucket,
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
# Dedup window: at most one email per event type per this many minutes (FR-018).
_DEDUP_WINDOW_MINUTES = 5


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
) -> tuple[dict[str, Any], str]:
    """Thin wrapper around aiosmtplib.send so tests can patch a single seam.

    Returns aiosmtplib's native `(per_recipient_errors, response_message)`. An
    empty errors dict indicates success; a non-empty dict maps each rejected
    recipient to its SMTP `(code, message_bytes)`.

    TLS policy: port 465 -> direct TLS; otherwise STARTTLS (auto-detected by
    aiosmtplib if the server advertises it).
    """
    use_tls = port == 465
    # start_tls=None lets aiosmtplib auto-detect STARTTLS based on server EHLO.
    # In production every real SMTP (Gmail / Workspace / school mail) advertises
    # STARTTLS; in tests aiosmtpd plain-mode does not — auto-detect handles both.
    return await aiosmtplib.send(
        message,
        hostname=hostname,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        start_tls=None,
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


def _fmt_taipei(dt: datetime) -> str:
    """Format a tz-aware datetime in UTC+8 (Taiwan local) for end-user emails."""
    from datetime import timedelta, timezone
    taipei = dt.astimezone(timezone(timedelta(hours=8)))
    return taipei.strftime("%Y-%m-%d %H:%M (UTC+8)")


def _public_base_url() -> str:
    from ai_api.config import get_settings
    base = (get_settings().base_url or "").rstrip("/")
    return base or "https://your-platform"


def _render_quarantine_email(event: NotificationEvent) -> tuple[str, str]:
    """Subject + plain-text body for allocation_quarantined event."""
    target_id_short = (event.target_id or "unknown")[:8]
    display = event.target_display_name or f"分配 {target_id_short}"
    details = event.details or {}
    last_hour = details.get("last_hour_calls")
    baseline = details.get("baseline_per_hour")
    reason = details.get("reason", "unknown")
    base_url = _public_base_url()

    subject = f"[AI API] 分配自動隔離 — {target_id_short}"
    why_line = (
        f"  - 觸發原因：過去 1 小時 {last_hour} calls，baseline {baseline:.1f}/hr"
        if isinstance(last_hour, int) and isinstance(baseline, (int, float))
        else f"  - 觸發原因：{reason}"
    )
    if isinstance(last_hour, int) and isinstance(baseline, (int, float)) and baseline > 0:
        ratio = last_hour / baseline
        why_line += f"（約 {ratio:.0f}× 基準值）"

    body = (
        "管理員您好，\n\n"
        "一筆分配剛剛被異常偵測器自動隔離。\n\n"
        f"  - 分配：{target_id_short}（{display}）\n"
        f"{why_line}\n"
        f"  - 時間：{_fmt_taipei(event.occurred_at)}\n\n"
        "請至以下頁面確認狀況並決定是否解除：\n"
        f"{base_url}/admin/observability/allocations\n\n"
        "— AI API Manager\n"
    )
    return subject, body


def _render_generic_email(event: NotificationEvent) -> tuple[str, str]:
    """Fallback template for event types without a dedicated renderer."""
    target_id_short = (event.target_id or "unknown")[:8]
    base_url = _public_base_url()
    subject = f"[AI API] {event.event_type} — {target_id_short}"
    details_dump = (
        ", ".join(f"{k}={v}" for k, v in (event.details or {}).items()) if event.details else "（無）"
    )
    body = (
        f"管理員您好，\n\n"
        f"事件 {event.event_type} 已發生。\n\n"
        f"  - 對象：{event.target_type or '-'} / {target_id_short}\n"
        f"  - 詳細：{details_dump}\n"
        f"  - 時間：{_fmt_taipei(event.occurred_at)}\n\n"
        f"請至管理後台查看：\n{base_url}/admin\n\n"
        "— AI API Manager\n"
    )
    return subject, body


def _render_upstream_burst_email(event: NotificationEvent) -> tuple[str, str]:
    details = event.details or {}
    count = details.get("failure_count", "?")
    window = details.get("window_minutes", "?")
    model = details.get("latest_model") or event.target_id or "（未知）"
    base_url = _public_base_url()
    subject = "[AI API] 上游連續失敗警示"
    body = (
        "管理員您好，\n\n"
        "偵測到上游 AI provider 在短時間內連續失敗，可能是 provider 故障或設定錯誤。\n\n"
        f"  - 失敗次數：過去 {window} 分鐘內 {count} 次\n"
        f"  - 最近失敗的 model：{model}\n"
        f"  - 時間：{_fmt_taipei(event.occurred_at)}\n\n"
        "請至以下頁面檢查 provider 憑證與用量：\n"
        f"{base_url}/admin/observability/usage\n\n"
        "— AI API Manager\n"
    )
    return subject, body


def _render_credential_invalid_email(event: NotificationEvent) -> tuple[str, str]:
    details = event.details or {}
    provider = details.get("provider") or "（未知）"
    cred_id = (event.target_id or "unknown")[:12]
    base_url = _public_base_url()
    subject = "[AI API] Provider 憑證失效"
    body = (
        "管理員您好，\n\n"
        "一張 provider 憑證在呼叫上游時驗證失敗（可能已被撤銷或過期）。\n\n"
        f"  - Provider：{provider}\n"
        f"  - 憑證：{cred_id}\n"
        f"  - 時間：{_fmt_taipei(event.occurred_at)}\n\n"
        "請至以下頁面更新或輪替該憑證：\n"
        f"{base_url}/admin/providers\n\n"
        "— AI API Manager\n"
    )
    return subject, body


_EVENT_RENDERERS = {
    "allocation_quarantined": _render_quarantine_email,
    "responses_upstream_error_burst": _render_upstream_burst_email,
    "provider_credential_auth_failed": _render_credential_invalid_email,
}


def render_event_email(event: NotificationEvent) -> tuple[str, str]:
    renderer = _EVENT_RENDERERS.get(event.event_type, _render_generic_email)
    return renderer(event)


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
        """Dispatch a real event notification to all configured recipients.

        US2 scope: no dedup yet — every matching event sends a fresh email.
        Dedup gate added in US4 (T054).
        """
        start = time.monotonic()
        # 1. Load config; absent / disabled / credentials_invalid -> skip.
        config = (
            await session.execute(select(NotificationConfig).limit(1))
        ).scalar_one_or_none()
        def latency_ms_so_far() -> int:
            return int((time.monotonic() - start) * 1000)

        if config is None or not config.enabled:
            return _persist_and_return_result(
                session=session,
                event_type=event.event_type,
                outcome=NotificationOutcome.skipped_disabled,
                recipients=[],
                subject="(skipped: notifications disabled)",
                body_preview="",
                per_recipient_status={},
                smtp_response_code=None,
                error_message=None,
                latency_ms=latency_ms_so_far(),
                audit_event_id=event.audit_event_id,
            )
        if config.status == NotificationConfigStatus.credentials_invalid:
            return _persist_and_return_result(
                session=session,
                event_type=event.event_type,
                outcome=NotificationOutcome.skipped_disabled,
                recipients=[],
                subject="(skipped: credentials invalid)",
                body_preview="",
                per_recipient_status={},
                smtp_response_code=None,
                error_message="config.status=credentials_invalid",
                latency_ms=latency_ms_so_far(),
                audit_event_id=event.audit_event_id,
            )
        if not config.recipients:
            return _persist_and_return_result(
                session=session,
                event_type=event.event_type,
                outcome=NotificationOutcome.skipped_no_recipients,
                recipients=[],
                subject="(skipped: no recipients)",
                body_preview="",
                per_recipient_status={},
                smtp_response_code=None,
                error_message=None,
                latency_ms=latency_ms_so_far(),
                audit_event_id=event.audit_event_id,
            )

        # 2. Decrypt password; if it fails, mark credentials_invalid and skip.
        try:
            password = decrypt_str(config.smtp_password_encrypted)
        except Exception as exc:
            config.status = NotificationConfigStatus.credentials_invalid
            await session.flush()
            return _persist_and_return_result(
                session=session,
                event_type=event.event_type,
                outcome=NotificationOutcome.skipped_disabled,
                recipients=[],
                subject="(skipped: decrypt failed)",
                body_preview="",
                per_recipient_status={},
                smtp_response_code=None,
                error_message=f"decrypt failed: {exc}",
                latency_ms=latency_ms_so_far(),
                audit_event_id=event.audit_event_id,
            )

        # 2b. Dedup gate (US4): if an active window already exists for this
        # event type, suppress this event (no email) and bump the bucket count.
        now = datetime.now(UTC)
        active_bucket = (
            await session.execute(
                select(NotificationDedupBucket)
                .where(
                    NotificationDedupBucket.event_type == event.event_type,
                    NotificationDedupBucket.window_end > now,
                )
                .order_by(NotificationDedupBucket.window_start.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if active_bucket is not None:
            active_bucket.event_count += 1
            active_bucket.last_event_at = now
            await session.flush()
            return _persist_and_return_result(
                session=session,
                event_type=event.event_type,
                outcome=NotificationOutcome.suppressed,
                recipients=[],
                subject="(suppressed: within dedup window)",
                body_preview="",
                per_recipient_status={},
                smtp_response_code=None,
                error_message=None,
                latency_ms=latency_ms_so_far(),
                audit_event_id=event.audit_event_id,
                dedup_bucket_id=active_bucket.id,
            )

        # No active window: open a new bucket. This is the event that sends.
        bucket = NotificationDedupBucket(
            id=str(ULID()),
            event_type=event.event_type,
            window_start=now,
            window_end=now + timedelta(minutes=_DEDUP_WINDOW_MINUTES),
            event_count=1,
            primary_record_id=None,  # set after the record is created
            last_event_at=now,
        )
        session.add(bucket)
        await session.flush()

        # 3. Render template.
        subject, body = render_event_email(event)
        msg = _build_message(
            sender_email=config.sender_email,
            sender_name=config.sender_name,
            recipients=config.recipients,
            subject=subject,
            body=body,
        )

        # 4. Send.
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
            # Mark every recipient ok by default; overwrite individual failures.
            per_recipient = dict.fromkeys(config.recipients, "ok")
            for addr, (err_code, err_msg) in (errors or {}).items():
                decoded = err_msg.decode(errors="replace") if isinstance(err_msg, bytes) else str(err_msg)
                per_recipient[addr] = f"{err_code}: {decoded}"
            if not errors:
                outcome = NotificationOutcome.sent
                smtp_code = 250 if response else None
            elif len(errors) == len(config.recipients):
                outcome = NotificationOutcome.send_failed_all_recipients
                first_code = next(iter(errors.values()))[0]
                smtp_code = int(first_code) if isinstance(first_code, int) else None
                error_message = f"all recipients rejected: {per_recipient}"
            else:
                # At least one delivered — count as sent per FR-021.
                outcome = NotificationOutcome.sent
                smtp_code = 250
        except BaseException as exc:
            outcome, smtp_code = classify_smtp_exception(exc, mode="send")
            per_recipient = dict.fromkeys(config.recipients, f"{outcome.value}: {exc}"[:200])
            error_message = str(exc)[:5000]
            logger.exception(
                "notify failed mode=send outcome=%s event_type=%s recipients_masked=%s",
                outcome.value, event.event_type,
                [_mask_email(r) for r in config.recipients],
            )

        result = _persist_and_return_result(
            session=session,
            event_type=event.event_type,
            outcome=outcome,
            recipients=list(config.recipients),
            subject=subject,
            body_preview=body[:500],
            per_recipient_status=per_recipient,
            smtp_response_code=smtp_code,
            error_message=error_message,
            latency_ms=latency_ms_so_far(),
            audit_event_id=event.audit_event_id,
            dedup_bucket_id=bucket.id,
        )
        # Link the bucket to its primary (the record that actually sent).
        bucket.primary_record_id = result.record_id
        await session.flush()
        return result

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
    audit_event_id: str | None = None,
    dedup_bucket_id: str | None = None,
) -> NotificationResult:
    record_id = str(ULID())
    record = NotificationRecord(
        id=record_id,
        event_type=event_type,
        audit_event_id=audit_event_id,
        dedup_bucket_id=dedup_bucket_id,
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
        record_id=record_id,
    )


# Re-export NotificationEvent/Result for callers that prefer importing from
# the email-specific module (matches existing pattern in other services).
__all__ = [
    "EmailNotifier",
    "NotificationEvent",
    "NotificationResult",
    "classify_smtp_exception",
]
