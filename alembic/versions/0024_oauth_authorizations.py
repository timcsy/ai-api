"""OAuth (Authorization Code + PKCE) — oauth_authorizations table.

New table backing first-party web-app authorization: a logged-in member consents
(picking allocations), a short-lived single-use `code` bound to the PKCE
challenge + redirect_uri is minted, then exchanged at /oauth/token for a
long-lived Credential. Pure additive; no mutual FK (avoids topological-sort trap).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_oauth_authorizations"
down_revision: str | Sequence[str] | None = "0023_bigint_token_quotas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_authorizations",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("client_name", sa.String(length=128), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=8), nullable=False),
        sa.Column("member_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("allocation_ids", sa.JSON(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("credential_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_oauth_auth_code", "oauth_authorizations", ["code"], unique=True)
    op.create_index("idx_oauth_auth_member", "oauth_authorizations", ["member_id"])
    op.create_index(
        "idx_oauth_auth_status_expires", "oauth_authorizations", ["status", "expires_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_oauth_auth_status_expires", table_name="oauth_authorizations")
    op.drop_index("idx_oauth_auth_member", table_name="oauth_authorizations")
    op.drop_index("idx_oauth_auth_code", table_name="oauth_authorizations")
    op.drop_table("oauth_authorizations")
