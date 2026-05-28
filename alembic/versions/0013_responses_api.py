"""responses_api — call_records token breakdown + price cached tier + stored_responses

Revision ID: 0013_responses_api
Revises: 0012_self_service
Create Date: 2026-05-28 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_responses_api"
down_revision: str | Sequence[str] | None = "0012_self_service"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("call_records") as batch:
        batch.add_column(sa.Column("reasoning_tokens", sa.Integer, nullable=True))
        batch.add_column(sa.Column("cached_tokens", sa.Integer, nullable=True))

    with op.batch_alter_table("price_list") as batch:
        batch.add_column(
            sa.Column("cached_input_per_1k_tokens_usd", sa.Numeric(12, 8), nullable=True)
        )

    op.create_table(
        "stored_responses",
        sa.Column("response_id", sa.String(64), primary_key=True),
        sa.Column(
            "allocation_id",
            sa.String(26),
            sa.ForeignKey("allocations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("upstream_response_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_stored_response_allocation", "stored_responses", ["allocation_id"]
    )
    op.create_index("idx_stored_response_expires", "stored_responses", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_stored_response_expires", table_name="stored_responses")
    op.drop_index("idx_stored_response_allocation", table_name="stored_responses")
    op.drop_table("stored_responses")
    with op.batch_alter_table("price_list") as batch:
        batch.drop_column("cached_input_per_1k_tokens_usd")
    with op.batch_alter_table("call_records") as batch:
        batch.drop_column("cached_tokens")
        batch.drop_column("reasoning_tokens")
