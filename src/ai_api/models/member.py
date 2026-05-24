"""Member ORM model — represents an authenticated user or external service."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_api.db import Base

if TYPE_CHECKING:
    from ai_api.models.allocation import Allocation
    from ai_api.models.session import Session


class MemberProvider(enum.StrEnum):
    google_oidc = "google_oidc"
    local_password = "local_password"
    external = "external"


class MemberStatus(enum.StrEnum):
    active = "active"
    disabled = "disabled"


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    provider: Mapped[MemberProvider] = mapped_column(
        Enum(MemberProvider, native_enum=False, length=32), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, native_enum=False, length=16),
        nullable=False,
        default=MemberStatus.active,
    )
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    # Phase 3b.2: admin role flag (c-β additive — session-based admin OR X-Admin-Token)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    allocations: Mapped[list[Allocation]] = relationship(back_populates="member")
    sessions: Mapped[list[Session]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_member_email", "email", unique=True),
        Index("idx_member_provider_external", "provider", "external_id"),
        Index("idx_member_status", "status"),
    )
