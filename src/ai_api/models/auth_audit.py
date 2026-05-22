"""AuthAuditLog ORM model — structured audit trail for auth-related events."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class AuditEventType(enum.StrEnum):
    login_success = "login_success"
    login_failure = "login_failure"
    logout = "logout"
    member_created = "member_created"
    member_disabled = "member_disabled"
    member_deleted = "member_deleted"
    whitelist_added = "whitelist_added"
    whitelist_removed = "whitelist_removed"
    rule_added = "rule_added"
    rule_removed = "rule_removed"
    restriction_added = "restriction_added"
    restriction_removed = "restriction_removed"
    password_changed = "password_changed"
    invitation_issued = "invitation_issued"
    invitation_used = "invitation_used"


class ActorType(enum.StrEnum):
    admin = "admin"
    member = "member"
    system = "system"
    anonymous = "anonymous"


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, native_enum=False, length=64), nullable=False
    )
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, native_enum=False, length=16), nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    redacted_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_audit_actor_time", "actor_type", "actor_id", "created_at"),
        Index("idx_audit_target_time", "target_type", "target_id", "created_at"),
        Index("idx_audit_event_time", "event_type", "created_at"),
    )
