"""Access control ORM models: EmailWhitelist, AutoRegisterRule, SourceRestriction."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class RuleType(enum.StrEnum):
    email_domain = "email_domain"


class EmailWhitelist(Base):
    __tablename__ = "email_whitelist"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    added_by: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AutoRegisterRule(Base):
    __tablename__ = "auto_register_rules"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    rule_type: Mapped[RuleType] = mapped_column(
        Enum(RuleType, native_enum=False, length=32), nullable=False
    )
    pattern: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (Index("idx_rule_enabled", "enabled", "rule_type"),)


class SourceRestriction(Base):
    __tablename__ = "source_restrictions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    # Postgres has CIDR but we use plain string for SQLite portability.
    cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_source_restriction_enabled", "enabled"),)
