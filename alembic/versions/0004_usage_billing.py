"""usage_billing — PriceList table + Allocation quota/service + CallRecord cost_usd

Revision ID: 0004_usage_billing
Revises: 0003_hardening
Create Date: 2026-05-22 13:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_usage_billing"
down_revision: str | Sequence[str] | None = "0003_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_CALL_OUTCOME = (
    "success",
    "rejected_unauthenticated",
    "rejected_revoked",
    "rejected_model_mismatch",
    "rejected_provider",
    "rejected_quarantined",
    "upstream_error",
    "gateway_error",
)
_NEW_CALL_OUTCOME = (
    *_OLD_CALL_OUTCOME[:6],
    "rejected_quota_exceeded",
    *_OLD_CALL_OUTCOME[6:],
)


def upgrade() -> None:
    op.create_table(
        "price_list",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_per_1k_tokens_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("output_per_1k_tokens_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "model", "effective_from", name="uq_pricelist_pme"),
    )
    op.create_index(
        "idx_pricelist_lookup",
        "price_list",
        ["provider", "model", "effective_from"],
    )

    with op.batch_alter_table("allocations") as batch:
        batch.add_column(sa.Column("quota_tokens_per_month", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "is_service_allocation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("call_records") as batch:
        batch.add_column(sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True))
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


def downgrade() -> None:
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
        batch.drop_column("cost_usd")

    with op.batch_alter_table("allocations") as batch:
        batch.drop_column("is_service_allocation")
        batch.drop_column("quota_tokens_per_month")

    op.drop_index("idx_pricelist_lookup", table_name="price_list")
    op.drop_table("price_list")
