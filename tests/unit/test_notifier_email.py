"""Phase 13 US1 T017: unit tests for EmailNotifier SMTP exception classification."""
from __future__ import annotations

import aiosmtplib
import pytest

from ai_api.models import NotificationOutcome
from ai_api.services.notifier_email import classify_smtp_exception


def test_classify_auth_error() -> None:
    exc = aiosmtplib.SMTPAuthenticationError(535, "auth failed")
    outcome, code = classify_smtp_exception(exc, mode="send")
    assert outcome == NotificationOutcome.send_failed_auth
    assert code == 535


def test_classify_auth_error_in_test_mode() -> None:
    exc = aiosmtplib.SMTPAuthenticationError(535, "auth failed")
    outcome, code = classify_smtp_exception(exc, mode="test")
    assert outcome == NotificationOutcome.test_failed_auth
    assert code == 535


def test_classify_connect_error() -> None:
    exc = aiosmtplib.SMTPConnectError("service not available")
    outcome, _ = classify_smtp_exception(exc, mode="send")
    assert outcome == NotificationOutcome.send_failed_connect


def test_classify_sender_refused() -> None:
    exc = aiosmtplib.SMTPSenderRefused(550, "sender rejected", "bot@example.com")
    outcome, _ = classify_smtp_exception(exc, mode="send")
    assert outcome == NotificationOutcome.send_failed_sender


def test_classify_os_error_as_connect_failure() -> None:
    exc = OSError("connection refused")
    outcome, code = classify_smtp_exception(exc, mode="send")
    assert outcome == NotificationOutcome.send_failed_connect
    assert code is None


def test_classify_unknown() -> None:
    exc = RuntimeError("something else")
    outcome, _ = classify_smtp_exception(exc, mode="send")
    assert outcome == NotificationOutcome.send_failed_unknown


@pytest.mark.parametrize(
    "exc_factory,mode,expected",
    [
        (lambda: aiosmtplib.SMTPAuthenticationError(535, "x"), "test", NotificationOutcome.test_failed_auth),
        (lambda: aiosmtplib.SMTPConnectError("x"), "test", NotificationOutcome.test_failed_connect),
        (lambda: aiosmtplib.SMTPSenderRefused(550, "x", "a@b"), "test", NotificationOutcome.test_failed_sender),
        (lambda: aiosmtplib.SMTPRecipientsRefused([]), "test", NotificationOutcome.test_failed_recipient),
        (lambda: RuntimeError("x"), "test", NotificationOutcome.test_failed_unknown),
    ],
)
def test_classify_table_for_test_mode(exc_factory, mode, expected) -> None:  # type: ignore[no-untyped-def]
    exc = exc_factory()
    outcome, _ = classify_smtp_exception(exc, mode=mode)
    assert outcome == expected
