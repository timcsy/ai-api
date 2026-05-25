"""Phase 5: MemberTag — many-to-many between Member and free-form tag strings.

First version intentionally avoids a separate Tag entity (YAGNI): tag names
are the distinct set of `MemberTag.tag` values. Adding a Tag table later is
a pure schema extension.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class MemberTag(Base):
    __tablename__ = "member_tags"

    member_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag: Mapped[str] = mapped_column(String(64), primary_key=True)
    added_by: Mapped[str] = mapped_column(String(64), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_member_tags_tag", "tag"),
        Index("idx_member_tags_member", "member_id"),
    )
