"""InvitationToken ORM model — single-use 48h-expiry token for first-time password set."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class InvitationToken(Base):
    __tablename__ = "invitation_tokens"

    token_fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    member_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("idx_invitation_member", "member_id"),
        Index("idx_invitation_expires", "expires_at"),
    )
