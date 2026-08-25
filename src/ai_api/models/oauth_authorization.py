"""OAuthAuthorization ORM model — first-party Authorization Code + PKCE flow.

One row per authorize attempt. A logged-in member consents (picking allocations),
which mints an authorization `code` bound to the PKCE `code_challenge` and the
`redirect_uri`; the app then exchanges that code (+ its `code_verifier`) at
/oauth/token for a long-lived Credential. Short-lived, single-use. No mutual FK
with other tables (avoids the topological-sort trap).
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class OAuthAuthStatus(enum.StrEnum):
    pending = "pending"    # consent created, awaiting approve/deny
    approved = "approved"  # code minted, awaiting token exchange
    consumed = "consumed"  # code exchanged for a credential (terminal)
    denied = "denied"
    expired = "expired"


class OAuthAuthorization(Base):
    __tablename__ = "oauth_authorizations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    # App-supplied, validated params.
    client_name: Mapped[str] = mapped_column(String(128), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(8), nullable=False, default="S256")
    # Consent is created by a logged-in member, so member_id is known up front.
    member_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[OAuthAuthStatus] = mapped_column(
        Enum(OAuthAuthStatus, native_enum=False, length=16),
        nullable=False,
        default=OAuthAuthStatus.pending,
    )
    # Set on approval.
    allocation_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    credential_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Consent window until approve; reset to a short code TTL on approve.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_oauth_auth_code", "code", unique=True),
        Index("idx_oauth_auth_member", "member_id"),
        Index("idx_oauth_auth_status_expires", "status", "expires_at"),
    )
