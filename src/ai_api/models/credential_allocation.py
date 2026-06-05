"""CredentialAllocation — Phase 20 association: which allocations a credential
(application key) may use (M:N).

`resource_model` is denormalised from the allocation (it is immutable per
allocation) so a `UNIQUE(credential_id, resource_model)` constraint guarantees a
call's model maps to at most one allocation in the key's scope (no billing
ambiguity), and the per-call resolution is a single indexed lookup.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class CredentialAllocation(Base):
    __tablename__ = "credential_allocations"

    credential_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("credentials.id", ondelete="CASCADE"), primary_key=True
    )
    allocation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("allocations.id", ondelete="CASCADE"), primary_key=True
    )
    # Denormalised from allocation.resource_model (immutable) for DB-level
    # uniqueness + single-query resolution by request model.
    resource_model: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("credential_id", "resource_model", name="uq_credential_model"),
        Index("idx_credalloc_allocation", "allocation_id"),
    )
