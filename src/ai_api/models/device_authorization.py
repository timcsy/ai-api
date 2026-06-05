"""DeviceAuthorization ORM model — Phase 19: RFC 8628-style device-flow.

One row per device-flow attempt. Short-lived, single-use. The install script
polls by `device_code`; the member approves in the browser (picking an
allocation), which mints a per-device Credential (Phase 18) and stashes its
plaintext **Fernet-encrypted** in `encrypted_token` for a single delivery on the
next poll, after which it is cleared.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class DeviceAuthStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    expired = "expired"


class DeviceAuthorization(Base):
    __tablename__ = "device_authorizations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    device_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    status: Mapped[DeviceAuthStatus] = mapped_column(
        Enum(DeviceAuthStatus, native_enum=False, length=16),
        nullable=False,
        default=DeviceAuthStatus.pending,
    )
    device_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Set on approval.
    member_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("members.id", ondelete="CASCADE"), nullable=True
    )
    allocation_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("allocations.id", ondelete="CASCADE"), nullable=True
    )
    credential_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True
    )
    # Fernet-encrypted plaintext token; delivered once on poll then cleared.
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    poll_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    __table_args__ = (
        Index("idx_device_auth_device_code", "device_code", unique=True),
        Index("idx_device_auth_user_code", "user_code", unique=True),
        Index("idx_device_auth_status_expires", "status", "expires_at"),
    )
