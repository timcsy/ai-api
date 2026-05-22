"""PriceList ORM model — append-only point-in-time pricing for upstream calls."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class PriceList(Base):
    __tablename__ = "price_list"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_per_1k_tokens_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    output_per_1k_tokens_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "model", "effective_from", name="uq_pricelist_pme"),
        Index("idx_pricelist_lookup", "provider", "model", "effective_from"),
    )
