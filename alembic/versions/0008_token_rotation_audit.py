"""token rotation audit event — extend AuditEventType enum

Revision ID: 0008_token_rotation_audit
Revises: 0007_member_is_admin
Create Date: 2026-05-24 23:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_token_rotation_audit"
down_revision: str | Sequence[str] | None = "0007_member_is_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD = (
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
    "member_promoted", "member_demoted",
)
_NEW = (*_OLD, "allocation_token_rotated")


def upgrade() -> None:
    with op.batch_alter_table("auth_audit_log") as batch:
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(*_OLD, name="auditeventtype", native_enum=False, length=64),
            type_=sa.Enum(*_NEW, name="auditeventtype", native_enum=False, length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("auth_audit_log") as batch:
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(*_NEW, name="auditeventtype", native_enum=False, length=64),
            type_=sa.Enum(*_OLD, name="auditeventtype", native_enum=False, length=64),
            existing_nullable=False,
        )
