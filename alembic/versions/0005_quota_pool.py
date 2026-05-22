"""quota_pool — RebalanceLog table + Allocation.quota_locked + audit enum

Revision ID: 0005_quota_pool
Revises: 0004_usage_billing
Create Date: 2026-05-22 15:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_quota_pool"
down_revision: str | Sequence[str] | None = "0004_usage_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_AUDIT = (
    "login_success", "login_failure", "logout",
    "member_created", "member_disabled", "member_deleted",
    "whitelist_added", "whitelist_removed",
    "rule_added", "rule_removed",
    "restriction_added", "restriction_removed",
    "password_changed",
    "invitation_issued", "invitation_used",
    "allocation_quarantined", "allocation_unquarantined",
    "anomaly_detector_run",
)
_NEW_AUDIT = (
    *_OLD_AUDIT,
    "quota_pool_rebalanced",
    "rebalance_failed",
    "pool_exhausted_by_reserved",
    "pool_idle",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.create_table(
        "rebalance_log",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("period_yyyymm", sa.String(length=6), nullable=False),
        sa.Column("triggered_by", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("T_before", sa.Integer(), nullable=False),
        sa.Column("T_after", sa.Integer(), nullable=False),
        sa.Column("scanned", sa.Integer(), nullable=False),
        sa.Column("changed", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=16), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index(
        "idx_rebalance_log_started_desc", "rebalance_log", ["started_at"]
    )

    if is_pg:
        # Partial UNIQUE: only enforce dedup on cron-triggered rebalances.
        op.create_index(
            "uq_rebalance_log_cron_month",
            "rebalance_log",
            ["period_yyyymm"],
            unique=True,
            postgresql_where=sa.text("triggered_by = 'cron'"),
        )
    else:
        # SQLite fallback: composite UNIQUE. Since 'cron' is the only string
        # subject to dedup, behaviour is equivalent.
        op.create_index(
            "uq_rebalance_log_period_trigger",
            "rebalance_log",
            ["period_yyyymm", "triggered_by"],
            unique=True,
        )

    with op.batch_alter_table("allocations") as batch:
        batch.add_column(
            sa.Column(
                "quota_locked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Extend AuditEventType enum (native_enum=False uses VARCHAR + CHECK; alter type).
    with op.batch_alter_table("auth_audit_log") as batch:
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(
                *_OLD_AUDIT, name="auditeventtype", native_enum=False, length=64
            ),
            type_=sa.Enum(
                *_NEW_AUDIT, name="auditeventtype", native_enum=False, length=64
            ),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("auth_audit_log") as batch:
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(
                *_NEW_AUDIT, name="auditeventtype", native_enum=False, length=64
            ),
            type_=sa.Enum(
                *_OLD_AUDIT, name="auditeventtype", native_enum=False, length=64
            ),
            existing_nullable=False,
        )

    with op.batch_alter_table("allocations") as batch:
        batch.drop_column("quota_locked")

    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.drop_index("uq_rebalance_log_cron_month", table_name="rebalance_log")
    else:
        op.drop_index("uq_rebalance_log_period_trigger", table_name="rebalance_log")
    op.drop_index("idx_rebalance_log_started_desc", table_name="rebalance_log")
    op.drop_table("rebalance_log")
