"""hardening — extend Allocation/AuditEventType/CallOutcome enums; index for per-IP rate limit

Revision ID: 0003_hardening
Revises: 0002_auth_membership
Create Date: 2026-05-22 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_hardening"
down_revision: str | Sequence[str] | None = "0002_auth_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_ALLOC_STATUS = ("active", "revoked", "quarantined")
_OLD_ALLOC_STATUS = ("active", "revoked")

_NEW_EVENT_TYPES = (
    "login_success",
    "login_failure",
    "logout",
    "member_created",
    "member_disabled",
    "member_deleted",
    "whitelist_added",
    "whitelist_removed",
    "rule_added",
    "rule_removed",
    "restriction_added",
    "restriction_removed",
    "password_changed",
    "invitation_issued",
    "invitation_used",
    "allocation_quarantined",
    "allocation_unquarantined",
    "anomaly_detector_run",
)

_NEW_CALL_OUTCOME = (
    "success",
    "rejected_unauthenticated",
    "rejected_revoked",
    "rejected_model_mismatch",
    "rejected_provider",
    "rejected_quarantined",
    "upstream_error",
    "gateway_error",
)
_OLD_CALL_OUTCOME = (
    "success",
    "rejected_unauthenticated",
    "rejected_revoked",
    "rejected_model_mismatch",
    "upstream_error",
    "gateway_error",
)


def upgrade() -> None:
    # Allocation.status: extend enum with "quarantined"
    with op.batch_alter_table("allocations") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.Enum(
                *_OLD_ALLOC_STATUS, name="allocationstatus", native_enum=False, length=16
            ),
            type_=sa.Enum(
                *_NEW_ALLOC_STATUS, name="allocationstatus", native_enum=False, length=16
            ),
            existing_nullable=False,
        )

    # AuthAuditLog.event_type: extend enum with 3 new values
    # (Re-spell the full enum to avoid divergence.)
    with op.batch_alter_table("auth_audit_log") as batch:
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(
                *(v for v in _NEW_EVENT_TYPES if v not in {"allocation_quarantined", "allocation_unquarantined", "anomaly_detector_run"}),
                name="auditeventtype",
                native_enum=False,
                length=64,
            ),
            type_=sa.Enum(
                *_NEW_EVENT_TYPES, name="auditeventtype", native_enum=False, length=64
            ),
            existing_nullable=False,
        )

    # CallRecord.outcome: extend enum
    with op.batch_alter_table("call_records") as batch:
        batch.alter_column(
            "outcome",
            existing_type=sa.Enum(
                *_OLD_CALL_OUTCOME, name="calloutcome", native_enum=False, length=32
            ),
            type_=sa.Enum(
                *_NEW_CALL_OUTCOME, name="calloutcome", native_enum=False, length=32
            ),
            existing_nullable=False,
        )

    # New index on password_attempts for per-IP rate limit
    op.create_index(
        "idx_attempt_source_ip_time",
        "password_attempts",
        ["source_ip", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_attempt_source_ip_time", table_name="password_attempts")

    with op.batch_alter_table("call_records") as batch:
        batch.alter_column(
            "outcome",
            existing_type=sa.Enum(
                *_NEW_CALL_OUTCOME, name="calloutcome", native_enum=False, length=32
            ),
            type_=sa.Enum(
                *_OLD_CALL_OUTCOME, name="calloutcome", native_enum=False, length=32
            ),
            existing_nullable=False,
        )

    with op.batch_alter_table("auth_audit_log") as batch:
        # Trimmed enum (drop the 3 new values).
        trimmed = tuple(
            v
            for v in _NEW_EVENT_TYPES
            if v not in {"allocation_quarantined", "allocation_unquarantined", "anomaly_detector_run"}
        )
        batch.alter_column(
            "event_type",
            existing_type=sa.Enum(
                *_NEW_EVENT_TYPES, name="auditeventtype", native_enum=False, length=64
            ),
            type_=sa.Enum(*trimmed, name="auditeventtype", native_enum=False, length=64),
            existing_nullable=False,
        )

    with op.batch_alter_table("allocations") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.Enum(
                *_NEW_ALLOC_STATUS, name="allocationstatus", native_enum=False, length=16
            ),
            type_=sa.Enum(
                *_OLD_ALLOC_STATUS, name="allocationstatus", native_enum=False, length=16
            ),
            existing_nullable=False,
        )
