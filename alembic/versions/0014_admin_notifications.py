"""admin_notifications — notification_config + notification_dedup_bucket + notification_record

Phase 13 — adds three tables for admin email notifications. No changes to existing tables.

Revision ID: 0014_admin_notifications
Revises: 0013_responses_api
Create Date: 2026-06-03 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_admin_notifications"
down_revision: str | Sequence[str] | None = "0013_responses_api"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("smtp_host", sa.String(255), nullable=False),
        sa.Column("smtp_port", sa.Integer, nullable=False, server_default="587"),
        sa.Column("smtp_username", sa.String(255), nullable=False),
        sa.Column("smtp_password_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("sender_email", sa.String(320), nullable=False),
        sa.Column(
            "sender_name", sa.String(128), nullable=False, server_default="AI API Manager"
        ),
        sa.Column("recipients", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "enabled", sa.Boolean, nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending_test"
        ),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_outcome", sa.String(32), nullable=True),
        sa.Column("last_test_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_notification_config_singleton"),
        sa.CheckConstraint(
            "smtp_port >= 1 AND smtp_port <= 65535",
            name="ck_notification_config_smtp_port_range",
        ),
    )

    op.create_table(
        "notification_record",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "audit_event_id",
            sa.String(26),
            sa.ForeignKey("auth_audit_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dedup_bucket_id", sa.String(26), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("recipients", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "per_recipient_status", sa.JSON, nullable=False, server_default="{}"
        ),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("body_preview", sa.String(500), nullable=False, server_default=""),
        sa.Column("smtp_response_code", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_record_created", "notification_record", ["created_at"])
    op.create_index(
        "idx_record_event_type", "notification_record", ["event_type", "created_at"]
    )

    op.create_table(
        "notification_dedup_bucket",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "primary_record_id",
            sa.String(26),
            sa.ForeignKey("notification_record.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_dedup_event_window",
        "notification_dedup_bucket",
        ["event_type", "window_end"],
    )

    # Add the FK from notification_record.dedup_bucket_id back to the bucket table
    # (deferred because the bucket table needs to exist first).
    with op.batch_alter_table("notification_record") as batch:
        batch.create_foreign_key(
            "fk_notification_record_dedup_bucket",
            "notification_dedup_bucket",
            ["dedup_bucket_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("notification_record") as batch:
        batch.drop_constraint(
            "fk_notification_record_dedup_bucket", type_="foreignkey"
        )
    op.drop_index("idx_dedup_event_window", table_name="notification_dedup_bucket")
    op.drop_table("notification_dedup_bucket")
    op.drop_index("idx_record_event_type", table_name="notification_record")
    op.drop_index("idx_record_created", table_name="notification_record")
    op.drop_table("notification_record")
    op.drop_table("notification_config")
