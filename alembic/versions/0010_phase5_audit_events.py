"""phase5_audit_events — extend AuditEventType enum with 8 Phase 5 events

Revision ID: 0010_phase5_audit_events
Revises: 0009_phase5_multiprovider_schema
Create Date: 2026-05-25 10:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_phase5_audit_events"
down_revision: str | Sequence[str] | None = "0009_phase5_multiprovider_schema"
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
    # Added by 0008_token_rotation_audit (Phase 011 hotfix)
    "allocation_token_rotated",
)
_NEW = (
    *_OLD,
    "provider_credential_created",
    "provider_credential_rotated",
    "provider_credential_disabled",
    "provider_credential_used_first_time",
    "member_tag_added",
    "member_tag_removed",
    "member_tag_bulk_added",
    "model_access_policy_updated",
)


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
