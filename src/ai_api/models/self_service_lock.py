"""Phase 6: SelfServiceReclaimLock — blocks a member from re-claiming a
self-service allocation for a model after an admin revoked it, until the
admin explicitly unlocks.

Composite PK (member_id, model_slug): one lock per pair, upsert-idempotent.
Admin unlock = delete the row.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class SelfServiceReclaimLock(Base):
    __tablename__ = "self_service_reclaim_locks"

    member_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model_slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("idx_self_service_lock_member", "member_id"),
    )
