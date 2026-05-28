"""StoredResponse ORM model — Phase 11.

Maps a platform-issued Responses `response_id` to the allocation that produced it,
so `previous_response_id` continuations can be attribution-isolated (an allocation
may only continue its own responses). Stores only the ownership + id mapping, not
the conversation content (the provider holds the context).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class StoredResponse(Base):
    __tablename__ = "stored_responses"

    response_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    allocation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("allocations.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    upstream_response_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_stored_response_allocation", "allocation_id"),
        Index("idx_stored_response_expires", "expires_at"),
    )
