"""model_catalog table

Revision ID: 0006_model_catalog
Revises: 0005_quota_pool
Create Date: 2026-05-23 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_model_catalog"
down_revision: str | Sequence[str] | None = "0005_quota_pool"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_catalog",
        sa.Column("slug", sa.String(length=128), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("modality_input", sa.JSON(), nullable=False),
        sa.Column("modality_output", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("cost_tier", sa.String(length=8), nullable=False),
        sa.Column("recommended_for", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("example_request", sa.JSON(), nullable=False),
        sa.Column("official_doc_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("deprecation_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_model_catalog_status", "model_catalog", ["status"])


def downgrade() -> None:
    op.drop_index("idx_model_catalog_status", table_name="model_catalog")
    op.drop_table("model_catalog")
