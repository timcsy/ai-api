"""phase5_multiprovider_schema — provider_credentials + member_tags + model_catalog access cols

Revision ID: 0009_phase5_multiprovider_schema
Revises: 0008_token_rotation_audit
Create Date: 2026-05-25 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_phase5_multiprovider_schema"
down_revision: str | Sequence[str] | None = "0008_token_rotation_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # provider_credentials
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("enc_key", sa.LargeBinary, nullable=False),
        sa.Column("fingerprint", sa.String(16), nullable=False),
        sa.Column("base_url", sa.String(256), nullable=True),
        sa.Column("extra_config", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "disabled", name="providercredentialstatus", native_enum=False, length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "label", name="uq_provider_credentials_provider_label"),
    )
    op.create_index(
        "idx_provider_credentials_routing",
        "provider_credentials",
        ["provider", "status", "last_used_at"],
    )

    # member_tags
    op.create_table(
        "member_tags",
        sa.Column(
            "member_id",
            sa.String(32),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tag", sa.String(64), primary_key=True),
        sa.Column("added_by", sa.String(64), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_member_tags_tag", "member_tags", ["tag"])
    op.create_index("idx_member_tags_member", "member_tags", ["member_id"])

    # model_catalog: add 3 access policy columns
    with op.batch_alter_table("model_catalog") as batch:
        batch.add_column(
            sa.Column(
                "default_access",
                sa.Enum("open", "restricted", name="defaultaccess", native_enum=False, length=16),
                nullable=False,
                server_default="open",
            )
        )
        batch.add_column(sa.Column("allowed_tags", sa.JSON, nullable=False, server_default="[]"))
        batch.add_column(sa.Column("denied_tags", sa.JSON, nullable=False, server_default="[]"))
    op.create_index("idx_model_catalog_provider", "model_catalog", ["provider"])


def downgrade() -> None:
    op.drop_index("idx_model_catalog_provider", table_name="model_catalog")
    with op.batch_alter_table("model_catalog") as batch:
        batch.drop_column("denied_tags")
        batch.drop_column("allowed_tags")
        batch.drop_column("default_access")
    op.drop_index("idx_member_tags_member", table_name="member_tags")
    op.drop_index("idx_member_tags_tag", table_name="member_tags")
    op.drop_table("member_tags")
    op.drop_index("idx_provider_credentials_routing", table_name="provider_credentials")
    op.drop_table("provider_credentials")
