"""CallRecord ORM model — one row per proxy call (success or reject)."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class CallOutcome(enum.StrEnum):
    success = "success"
    rejected_unauthenticated = "rejected_unauthenticated"
    rejected_revoked = "rejected_revoked"
    rejected_model_mismatch = "rejected_model_mismatch"
    rejected_provider = "rejected_provider"
    rejected_quarantined = "rejected_quarantined"
    rejected_paused = "rejected_paused"
    rejected_quota_exceeded = "rejected_quota_exceeded"
    upstream_error = "upstream_error"
    gateway_error = "gateway_error"


class CallRecord(Base):
    __tablename__ = "call_records"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    allocation_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("allocations.id", ondelete="SET NULL"), nullable=True
    )
    subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    outcome: Mapped[CallOutcome] = mapped_column(
        Enum(CallOutcome, native_enum=False, length=32), nullable=False
    )
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Phase 3a: point-in-time cost. NULL when no PriceList match was found.
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_callrecord_allocation_time", "allocation_id", "started_at"),
        Index("idx_callrecord_outcome_time", "outcome", "started_at"),
    )
