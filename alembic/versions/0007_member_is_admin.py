"""member_is_admin — add Member.is_admin + member_promoted/demoted audit events

Revision ID: 0007_member_is_admin
Revises: 0006_model_catalog
Create Date: 2026-05-24 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_member_is_admin"
down_revision: str | Sequence[str] | None = "0006_model_catalog"
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
    "quota_pool_rebalanced", "rebalance_failed",
    "pool_exhausted_by_reserved", "pool_idle",
)
_NEW_AUDIT = (*_OLD_AUDIT, "member_promoted", "member_demoted")


def upgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.add_column(
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

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

    with op.batch_alter_table("members") as batch:
        batch.drop_column("is_admin")
