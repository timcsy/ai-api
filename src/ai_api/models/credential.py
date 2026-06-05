"""Credential ORM model — Phase 20: a credential is a member-owned, named
application key whose scope is a SET of the member's allocations (M:N).

Persists fingerprint, not plaintext. Each call resolves the matching allocation
by request model (see CredentialAllocation). Phase 18's "one credential per
allocation" is now the special case of a scope containing a single allocation.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_api.db import Base
from ai_api.models.credential_allocation import CredentialAllocation

if TYPE_CHECKING:
    from ai_api.models.allocation import Allocation
    from ai_api.models.member import Member


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    # Phase 20: owner is the member; scope is a set of the member's allocations.
    member_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    member: Mapped[Member] = relationship(back_populates="credentials")
    # scope: the allocations this key may use (M:N via CredentialAllocation).
    allocations: Mapped[list[Allocation]] = relationship(
        secondary=CredentialAllocation.__table__,
        back_populates="credentials",
    )

    __table_args__ = (
        Index("idx_credential_fingerprint", "token_fingerprint", unique=True),
        Index("idx_credential_member", "member_id"),
    )
