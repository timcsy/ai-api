"""RebalanceLog ORM model — append-only audit of successful quota-pool rebalances.

Phase 3c FR-011~FR-013. Failures do NOT write here; they go to AuthAuditLog
as `rebalance_failed`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class RebalanceLog(Base):
    __tablename__ = "rebalance_log"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    period_yyyymm: Mapped[str] = mapped_column(String(6), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    T_before: Mapped[int] = mapped_column(Integer, nullable=False)
    T_after: Mapped[int] = mapped_column(Integer, nullable=False)
    scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    changed: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        # Postgres uses partial UNIQUE (see migration 0005); SQLite degrades to
        # composite UNIQUE (period_yyyymm, triggered_by) — equivalent since
        # 'cron' is the only string subject to dedup.
        UniqueConstraint("period_yyyymm", "triggered_by", name="uq_rebalance_log_period_trigger"),
        Index("idx_rebalance_log_started_desc", "started_at"),
    )
