"""Phase 39 (spec 053): adaptive quota-pool settings as a DB singleton.

Holds the pool total T and per-allocation floor — moved out of Helm/env so admins
can edit them in the UI. Exactly one row, enforced via CHECK (id = 1) (same idiom
as notification_config). The read path (services.quota_pool.get_pool_config)
lazy-seeds this row from settings on first access, so first run is a no-op change.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class PoolConfig(Base):
    """Singleton config — exactly one row enforced via CHECK (id = 1)."""

    __tablename__ = "pool_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_tokens_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    floor_per_allocation: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_pool_config_singleton"),
        CheckConstraint("total_tokens_per_month >= 0", name="ck_pool_config_total_nonneg"),
        CheckConstraint("floor_per_allocation >= 0", name="ck_pool_config_floor_nonneg"),
    )
