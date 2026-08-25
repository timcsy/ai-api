"""OAuth config singleton — admin-editable redirect_uri allowlist.

Singleton table (CHECK id=1), same idiom as pool_config / anomaly_config. Lets
admins edit the OAuth redirect allowlist at runtime; lazy-seeds from
settings.OAUTH_REDIRECT_ALLOWLIST on first read. Pure additive.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_oauth_config"
down_revision: str | Sequence[str] | None = "0024_oauth_authorizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("redirect_allowlist", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_oauth_config_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("oauth_config")
