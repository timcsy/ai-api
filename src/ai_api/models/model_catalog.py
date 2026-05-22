"""ModelCatalog ORM model — Phase 4.

Describes one AI model entry. list-valued fields stored as JSON columns
(Postgres JSONB / SQLite JSON), per research.md §1.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class ModelCatalog(Base):
    __tablename__ = "model_catalog"

    slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    modality_input: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    modality_output: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_tier: Mapped[str] = mapped_column(String(8), nullable=False)
    recommended_for: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    example_request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    official_doc_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    deprecation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("idx_model_catalog_status", "status"),)
