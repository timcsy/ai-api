"""self_service — catalog opt-in + allocation origin + reclaim locks

Revision ID: 0012_self_service
Revises: 0011_tag_rules
Create Date: 2026-05-26 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_self_service"
down_revision: str | Sequence[str] | None = "0011_tag_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_catalog") as batch:
        batch.add_column(
            sa.Column(
                "self_service_enabled",
                sa.Boolean,
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("self_service_default_quota", sa.Integer, nullable=True))

    with op.batch_alter_table("allocations") as batch:
        batch.add_column(
            sa.Column(
                "origin",
                sa.Enum("admin", "self_service", name="allocationorigin", native_enum=False, length=16),
                nullable=False,
                server_default="admin",
            )
        )

    op.create_table(
        "self_service_reclaim_locks",
        sa.Column(
            "member_id",
            sa.String(26),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("model_slug", sa.String(128), primary_key=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(128), nullable=False),
    )
    op.create_index(
        "idx_self_service_lock_member", "self_service_reclaim_locks", ["member_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_self_service_lock_member", table_name="self_service_reclaim_locks")
    op.drop_table("self_service_reclaim_locks")
    with op.batch_alter_table("allocations") as batch:
        batch.drop_column("origin")
    with op.batch_alter_table("model_catalog") as batch:
        batch.drop_column("self_service_default_quota")
        batch.drop_column("self_service_enabled")
