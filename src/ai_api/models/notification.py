"""Phase 13: admin email notification storage models.

Three tables:
  - notification_config: singleton (CHECK id=1) holding SMTP creds + recipients
  - notification_dedup_bucket: one row per (event_type, 5-min window) for suppression
  - notification_record: per-event audit row (sent / suppressed / skipped / failed)

All sensitive values (SMTP password) Fernet-encrypted at rest via the existing
PROVIDER_KEY_ENC_KEY; service layer handles encryption/decryption.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class NotificationConfigStatus(enum.StrEnum):
    pending_test = "pending_test"
    verified = "verified"
    credentials_invalid = "credentials_invalid"


class NotificationOutcome(enum.StrEnum):
    sent = "sent"
    suppressed = "suppressed"
    skipped_disabled = "skipped_disabled"
    skipped_no_recipients = "skipped_no_recipients"
    send_failed_auth = "send_failed_auth"
    send_failed_connect = "send_failed_connect"
    send_failed_sender = "send_failed_sender"
    send_failed_all_recipients = "send_failed_all_recipients"
    send_failed_unknown = "send_failed_unknown"
    test_sent = "test_sent"
    test_failed_auth = "test_failed_auth"
    test_failed_connect = "test_failed_connect"
    test_failed_sender = "test_failed_sender"
    test_failed_recipient = "test_failed_recipient"
    test_failed_unknown = "test_failed_unknown"


class NotificationConfig(Base):
    """Singleton config — exactly one row enforced via CHECK (id = 1)."""

    __tablename__ = "notification_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False)
    # Fernet ciphertext; decrypted via PROVIDER_KEY_ENC_KEY (same pattern as
    # ProviderCredential.enc_key — see services/crypto.py encrypt_str/decrypt_str)
    smtp_password_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="AI API Manager"
    )
    # JSON list of email strings
    recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[NotificationConfigStatus] = mapped_column(
        String(32), nullable=False, default=NotificationConfigStatus.pending_test
    )
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_notification_config_singleton"),
        CheckConstraint(
            "smtp_port >= 1 AND smtp_port <= 65535", name="ck_notification_config_smtp_port_range"
        ),
    )


class NotificationDedupBucket(Base):
    """5-minute dedup window per event_type. New events within the same active
    window are suppressed (no email sent); count tracks total occurrences."""

    __tablename__ = "notification_dedup_bucket"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Points to the notification_record that triggered this bucket (the one that
    # actually sent the email). Nullable so record deletion cascades to SET NULL
    # without orphaning the bucket.
    #
    # use_alter=True breaks the mutual FK cycle with notification_record
    # (record.dedup_bucket_id -> bucket.id). Without it, metadata.create_all /
    # drop_all on Postgres raises CircularDependencyError because the tables
    # can't be topologically sorted; use_alter emits this constraint as a
    # separate ALTER TABLE after both tables exist.
    primary_record_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey(
            "notification_record.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_dedup_bucket_primary_record",
        ),
        nullable=True,
    )
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_dedup_event_window", "event_type", "window_end"),
    )


class NotificationRecord(Base):
    """One row per notification attempt (sent, suppressed, skipped, failed)."""

    __tablename__ = "notification_record"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_event_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("auth_audit_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    dedup_bucket_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("notification_dedup_bucket.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome: Mapped[NotificationOutcome] = mapped_column(String(32), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # {"alice@example.com": "ok", "bob@example.com": "rejected: mailbox unavailable"}
    per_recipient_status: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    # First 500 chars of body; full body not stored (save space, may contain PII)
    body_preview: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    smtp_response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Convenience non-mapped attribute: populated by service-layer JOIN when
    # this record is a bucket's primary. None for non-primary records.
    bucket_event_count_view: ClassVar[Any] = None

    __table_args__ = (
        Index("idx_record_created", "created_at"),
        Index("idx_record_event_type", "event_type", "created_at"),
    )
