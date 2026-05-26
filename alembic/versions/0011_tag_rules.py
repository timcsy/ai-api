"""tag_rules — auto-tagging rules + member_tags.source/rule_id

Revision ID: 0011_tag_rules
Revises: 0010_phase5_audit_events
Create Date: 2026-05-26 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_tag_rules"
down_revision: str | Sequence[str] | None = "0010_phase5_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tag_rules",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column(
            "matcher_type",
            sa.Enum(
                "email_localpart_regex",
                "email_suffix",
                "email_domain",
                "always",
                name="matchertype",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("pattern", sa.String(256), nullable=False, server_default=""),
        sa.Column("tag", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
    )
    op.create_index("idx_tag_rules_eval", "tag_rules", ["enabled", "order_index"])

    with op.batch_alter_table("member_tags") as batch:
        batch.add_column(
            sa.Column(
                "source",
                sa.Enum("manual", "auto", name="tagsource", native_enum=False, length=16),
                nullable=False,
                server_default="manual",
            )
        )
        batch.add_column(sa.Column("rule_id", sa.String(32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("member_tags") as batch:
        batch.drop_column("rule_id")
        batch.drop_column("source")
    op.drop_index("idx_tag_rules_eval", table_name="tag_rules")
    op.drop_table("tag_rules")
