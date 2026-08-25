"""OAuthConfig — singleton, admin-editable OAuth settings (redirect allowlist).

Exactly one row (CHECK id = 1), same idiom as pool_config / anomaly_config. The
redirect_uri allowlist lives here so admins can edit it at runtime instead of a
redeploy; it lazy-seeds from settings.OAUTH_REDIRECT_ALLOWLIST on first read, so
the env→DB move is a no-op on first run and the env stays a bootstrap default.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class OAuthConfig(Base):
    """Singleton config — exactly one row enforced via CHECK (id = 1)."""

    __tablename__ = "oauth_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Comma/newline-separated redirect_uri prefixes an app may be handed a code
    # back to. Empty ⇒ /oauth/authorize is refused (fail-closed).
    redirect_allowlist: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (CheckConstraint("id = 1", name="ck_oauth_config_singleton"),)
