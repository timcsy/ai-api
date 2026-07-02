"""Phase (054): anomaly-detector settings as an admin-editable DB singleton.

Additive: new singleton table `anomaly_config` (CHECK id = 1) holding the
auto-quarantine switch, an optional pause-until, and the detection thresholds.
The read path lazy-seeds the single row from settings on first access, so there's
no data to migrate and first run is a no-op behaviour change.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_anomaly_config"
down_revision: str | Sequence[str] | None = "0021_pool_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anomaly_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "auto_quarantine_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("pause_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("threshold_multiplier", sa.Float(), nullable=False, server_default="10"),
        sa.Column("min_calls", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("absolute_cold_start", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("baseline_min_calls", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_anomaly_config_singleton"),
        sa.CheckConstraint("threshold_multiplier >= 1", name="ck_anomaly_config_multiplier"),
        sa.CheckConstraint("min_calls >= 0", name="ck_anomaly_config_min_calls"),
        sa.CheckConstraint("absolute_cold_start >= 0", name="ck_anomaly_config_abs"),
        sa.CheckConstraint("baseline_min_calls >= 0", name="ck_anomaly_config_baseline_min"),
    )


def downgrade() -> None:
    op.drop_table("anomaly_config")
