"""Credential ORM model — Phase 18: 1:N with Allocation (per-device tokens).

A single allocation can hold many independent named credentials (one per
device); each is independently revocable. Persists fingerprint, not plaintext.
"""
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

    # Phase 18: independent PK so an allocation can have many credentials.
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    allocation_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("allocations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Phase 18: last successful use (throttled update) + soft revoke.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    allocation: Mapped[Allocation] = relationship(back_populates="credentials")

    __table_args__ = (
        Index("idx_credential_fingerprint", "token_fingerprint", unique=True),
        Index("idx_credential_allocation", "allocation_id"),
    )
