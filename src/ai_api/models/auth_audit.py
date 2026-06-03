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
    allocation_quarantined = "allocation_quarantined"
    allocation_unquarantined = "allocation_unquarantined"
    anomaly_detector_run = "anomaly_detector_run"
    # Phase 3c
    quota_pool_rebalanced = "quota_pool_rebalanced"
    rebalance_failed = "rebalance_failed"
    pool_exhausted_by_reserved = "pool_exhausted_by_reserved"
    pool_idle = "pool_idle"
    # Phase 3b.2
    member_promoted = "member_promoted"
    member_demoted = "member_demoted"
    # Phase 011 hotfix — self-service token rotation
    allocation_token_rotated = "allocation_token_rotated"
    # Phase 5 — multi-provider + tag access
    provider_credential_created = "provider_credential_created"
    provider_credential_rotated = "provider_credential_rotated"
    provider_credential_disabled = "provider_credential_disabled"
    provider_credential_used_first_time = "provider_credential_used_first_time"
    member_tag_added = "member_tag_added"
    member_tag_removed = "member_tag_removed"
    member_tag_bulk_added = "member_tag_bulk_added"
    model_access_policy_updated = "model_access_policy_updated"
    # Phase 6: self-service allocation
    self_service_claimed = "self_service_claimed"
    self_service_reclaim_locked = "self_service_reclaim_locked"
    self_service_unlocked = "self_service_unlocked"
    # Phase 7: price list admin
    price_version_added = "price_version_added"
    # Phase 019: allocation pause/resume (reversible, token-preserving)
    allocation_paused = "allocation_paused"
    allocation_resumed = "allocation_resumed"
    # Phase 13: admin email notifications — event types that trigger admin emails
    responses_upstream_error_burst = "responses_upstream_error_burst"
    provider_credential_auth_failed = "provider_credential_auth_failed"
    allocation_daily_cap_exceeded = "allocation_daily_cap_exceeded"


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
