"""Phase 5: ProviderCredential — admin-managed LLM provider API key.

Fernet-encrypted at rest; plaintext shown ONCE on create/rotate. Round-robin
selection by `last_used_at` ASC NULLS FIRST when multiple active credentials
exist for the same provider.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class ProviderCredentialStatus(enum.StrEnum):
    active = "active"
    disabled = "disabled"


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    enc_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extra_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ProviderCredentialStatus] = mapped_column(
        Enum(ProviderCredentialStatus, native_enum=False, length=16),
        nullable=False,
        default=ProviderCredentialStatus.active,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "label", name="uq_provider_credentials_provider_label"),
        Index(
            "idx_provider_credentials_routing", "provider", "status", "last_used_at"
        ),
    )
