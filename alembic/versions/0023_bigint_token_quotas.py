"""Widen token-quota columns INT4 → BIGINT (spec/bugfix).

Monthly token quotas can legitimately exceed INT4's max (~2.147e9) — e.g. a
10e9 self-service default. On Postgres, writing such a value to an INTEGER column
raised "integer out of range" → 500 ("更新失敗"). Widen to BIGINT.

SQLite stores INTEGER as up to 8 bytes already, so this is a no-op there (and
Alembic can't ALTER COLUMN TYPE on SQLite without a table rebuild) — guarded by
dialect. Widening INT4→INT8 on Postgres is a safe, no-data-loss change.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_bigint_token_quotas"
down_revision: str | Sequence[str] | None = "0022_anomaly_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLS = [
    ("allocations", "quota_tokens_per_month", True),
    ("model_catalog", "self_service_default_quota", True),
    ("pool_config", "total_tokens_per_month", False),
]


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return  # SQLite INTEGER is already 64-bit; nothing to widen
    for table, col, nullable in _COLS:
        op.alter_column(table, col, type_=sa.BigInteger(), existing_type=sa.Integer(),
                        existing_nullable=nullable)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    for table, col, nullable in _COLS:
        op.alter_column(table, col, type_=sa.Integer(), existing_type=sa.BigInteger(),
                        existing_nullable=nullable)
