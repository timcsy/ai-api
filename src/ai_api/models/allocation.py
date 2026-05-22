"""Allocation ORM model — represents a unit of resource granted to a subject."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_api.db import Base

if TYPE_CHECKING:
    from ai_api.models.credential import Credential
    from ai_api.models.member import Member


class AllocationStatus(enum.StrEnum):
    active = "active"
    revoked = "revoked"


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

    credential: Mapped[Credential] = relationship(
        back_populates="allocation", uselist=False, cascade="all, delete-orphan"
    )
    member: Mapped[Member] = relationship(back_populates="allocations")

    __table_args__ = (
        Index("idx_allocation_member", "member_id", "created_at"),
        Index("idx_allocation_status", "status"),
    )
