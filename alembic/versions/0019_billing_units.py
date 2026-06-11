"""Phase 29 ② (040): billing generalization — non-token units.

Additive, nullable columns (zero regression for token billing):
  price_list:   price_unit (NULL ⇒ token), price_per_unit_usd
  call_records: quantity, unit (NULL ⇒ token)
Existing rows stay NULL and keep using the token columns unchanged.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_billing_units"
down_revision: str | Sequence[str] | None = "0018_model_litellm_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("price_list", sa.Column("price_unit", sa.String(length=16), nullable=True))
    op.add_column(
        "price_list", sa.Column("price_per_unit_usd", sa.Numeric(12, 8), nullable=True)
    )
    op.add_column("call_records", sa.Column("quantity", sa.Integer(), nullable=True))
    op.add_column("call_records", sa.Column("unit", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("call_records", "unit")
    op.drop_column("call_records", "quantity")
    op.drop_column("price_list", "price_per_unit_usd")
    op.drop_column("price_list", "price_unit")
