"""PasswordAttempt ORM model — rate-limit + audit log for login attempts."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class AttemptOutcome(enum.StrEnum):
    success = "success"
    bad_password = "bad_password"
    unknown_email = "unknown_email"
    locked = "locked"
    disabled = "disabled"


class PasswordAttempt(Base):
    __tablename__ = "password_attempts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[AttemptOutcome] = mapped_column(
        Enum(AttemptOutcome, native_enum=False, length=32), nullable=False
    )

    __table_args__ = (Index("idx_attempt_email_time", "email", "attempted_at"),)
