"""Phase 33 (046): cost-based monthly quota — per-allocation USD spend cap.

Additive, nullable column (zero regression for token quota):
  allocations: quota_cost_usd_per_month (NULL ⇒ no cost cap)
Existing rows stay NULL and keep using quota_tokens_per_month unchanged.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_cost_quota"
down_revision: str | Sequence[str] | None = "0019_billing_units"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "allocations",
        sa.Column("quota_cost_usd_per_month", sa.Numeric(10, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("allocations", "quota_cost_usd_per_month")
