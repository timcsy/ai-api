"""Phase 39 (053): adaptive quota-pool settings as a DB singleton.

Additive: new singleton table `pool_config` (CHECK id = 1) holding the pool total
T and per-allocation floor — moved out of Helm/env so admins can edit in the UI.
The read path lazy-seeds the single row from settings on first access, so there's
no data to migrate and first run is a no-op behaviour change.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_pool_config"
down_revision: str | Sequence[str] | None = "0020_cost_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pool_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("total_tokens_per_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("floor_per_allocation", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_pool_config_singleton"),
        sa.CheckConstraint("total_tokens_per_month >= 0", name="ck_pool_config_total_nonneg"),
        sa.CheckConstraint("floor_per_allocation >= 0", name="ck_pool_config_floor_nonneg"),
    )


def downgrade() -> None:
    op.drop_table("pool_config")
