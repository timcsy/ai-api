"""Phase 19: device-flow — device_authorizations table.

New table backing the RFC 8628-style device-flow (Codex one-line install). Pure
additive: one row per device-flow attempt; short-lived, single-use. No mutual
FK with any other table (avoids the topological-sort trap of mutual FKs).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_device_authorizations"
down_revision: str | Sequence[str] | None = "0015_per_device_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_authorizations",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("user_code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("device_label", sa.String(length=64), nullable=True),
        sa.Column("member_id", sa.String(length=26), nullable=True),
        sa.Column("allocation_id", sa.String(length=26), nullable=True),
        sa.Column("credential_id", sa.String(length=26), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("poll_interval", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["allocation_id"], ["allocations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code"),
        sa.UniqueConstraint("user_code"),
    )
    op.create_index(
        "idx_device_auth_device_code", "device_authorizations", ["device_code"], unique=True
    )
    op.create_index(
        "idx_device_auth_user_code", "device_authorizations", ["user_code"], unique=True
    )
    op.create_index(
        "idx_device_auth_status_expires",
        "device_authorizations",
        ["status", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_device_auth_status_expires", table_name="device_authorizations")
    op.drop_index("idx_device_auth_user_code", table_name="device_authorizations")
    op.drop_index("idx_device_auth_device_code", table_name="device_authorizations")
    op.drop_table("device_authorizations")
