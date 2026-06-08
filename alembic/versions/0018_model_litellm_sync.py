"""Phase 23: add model_catalog.litellm_sync (LiteLLM registry provenance).

Additive, nullable JSON column — existing rows stay NULL (zero regression).
Holds {base_model_key, imported_version, field_sources, snapshot}.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_model_litellm_sync"
down_revision: str | Sequence[str] | None = "0017_scoped_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_catalog", sa.Column("litellm_sync", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_catalog", "litellm_sync")
