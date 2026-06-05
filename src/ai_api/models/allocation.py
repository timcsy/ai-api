"""Allocation ORM model — represents a unit of resource granted to a subject."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_api.db import Base

if TYPE_CHECKING:
    from ai_api.models.credential import Credential
    from ai_api.models.member import Member


class AllocationStatus(enum.StrEnum):
    active = "active"
    revoked = "revoked"
    quarantined = "quarantined"
    paused = "paused"  # admin manual, reversible (vs revoked=terminal, quarantined=auto)


class AllocationOrigin(enum.StrEnum):
    admin = "admin"
    self_service = "self_service"


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    member_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("members.id", ondelete="RESTRICT"), nullable=False
    )
    subject_snapshot: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[AllocationStatus] = mapped_column(
        Enum(AllocationStatus, native_enum=False, length=16),
        nullable=False,
        default=AllocationStatus.active,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 3a
    quota_tokens_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_service_allocation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phase 3c
    quota_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phase 6
    origin: Mapped[AllocationOrigin] = mapped_column(
        Enum(AllocationOrigin, native_enum=False, length=16),
        nullable=False,
        default=AllocationOrigin.admin,
    )

    # Phase 20: M:N — credentials (application keys) whose scope includes this
    # allocation. (Phase 18's 1:N is the single-allocation-scope special case.)
    credentials: Mapped[list[Credential]] = relationship(
        secondary="credential_allocations", back_populates="allocations"
    )
    member: Mapped[Member] = relationship(back_populates="allocations")

    __table_args__ = (
        Index("idx_allocation_member", "member_id", "created_at"),
        Index("idx_allocation_status", "status"),
    )
