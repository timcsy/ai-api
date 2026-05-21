"""Credential ORM model — 1:1 with Allocation; persists fingerprint, not plaintext."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_api.db import Base

if TYPE_CHECKING:
    from ai_api.models.allocation import Allocation


class Credential(Base):
    __tablename__ = "credentials"

    allocation_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("allocations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    allocation: Mapped[Allocation] = relationship(back_populates="credential")

    __table_args__ = (
        Index("idx_credential_fingerprint", "token_fingerprint", unique=True),
    )
