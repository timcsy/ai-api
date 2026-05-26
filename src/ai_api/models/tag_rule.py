"""Phase 5.2: TagRule — admin-defined ordered rules that auto-assign a tag at
member first registration.

Evaluation is first-match-wins by ascending ``order_index``. ``always`` matcher
acts as a catch-all fallback. See specs/014-auto-tag-rules/.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class MatcherType(enum.StrEnum):
    email_localpart_regex = "email_localpart_regex"
    email_suffix = "email_suffix"
    email_domain = "email_domain"
    always = "always"


class TagRule(Base):
    __tablename__ = "tag_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    matcher_type: Mapped[MatcherType] = mapped_column(
        Enum(MatcherType, native_enum=False, length=32), nullable=False
    )
    pattern: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_tag_rules_eval", "enabled", "order_index"),
    )
