"""Phase 18: per-device credentials — credentials 1:1 → 1:N.

Rebuilds the ``credentials`` table so an allocation can hold many independent
per-device credentials:

* primary key moves from ``allocation_id`` to an independent ULID ``id``;
* ``allocation_id`` becomes an ordinary (non-unique) indexed FK;
* adds ``name`` (device label), ``last_used_at`` and ``revoked_at``;
* ``token_fingerprint`` stays UNIQUE (token → credential is still 1-hit).

Existing rows are preserved verbatim — same ``token_fingerprint`` /
``token_prefix`` / ``created_at`` — so **every existing token keeps working**.
Each migrated row gets a fresh ULID ``id`` and ``name = "預設"``.

Done via build-new-table + copy + swap so it runs identically on SQLite and
PostgreSQL (changing the PK is not an in-place ALTER on SQLite).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from ulid import ULID

from alembic import op

revision: str = "0015_per_device_credentials"
down_revision: str | Sequence[str] | None = "0014_admin_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_CREDENTIAL_NAME = "預設"

_NEW_COLUMNS = (
    sa.Column("id", sa.String(length=26), nullable=False),
    sa.Column("allocation_id", sa.String(length=26), nullable=False),
    sa.Column("name", sa.String(length=64), nullable=False),
    sa.Column("token_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("token_prefix", sa.String(length=8), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
)


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(
        sa.text(
            "SELECT allocation_id, token_fingerprint, token_prefix, created_at "
            "FROM credentials"
        )
    ).mappings().all()

    op.drop_index("idx_credential_fingerprint", table_name="credentials")
    op.create_table(
        "credentials_new",
        *_NEW_COLUMNS,
        sa.ForeignKeyConstraint(["allocation_id"], ["allocations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_fingerprint"),
    )

    if existing:
        op.bulk_insert(
            sa.table("credentials_new", *(sa.column(c.name) for c in _NEW_COLUMNS)),
            [
                {
                    "id": str(ULID()),
                    "allocation_id": row["allocation_id"],
                    "name": DEFAULT_CREDENTIAL_NAME,
                    "token_fingerprint": row["token_fingerprint"],
                    "token_prefix": row["token_prefix"],
                    "created_at": row["created_at"],
                    "last_used_at": None,
                    "revoked_at": None,
                }
                for row in existing
            ],
        )

    op.drop_table("credentials")
    op.rename_table("credentials_new", "credentials")
    op.create_index(
        "idx_credential_fingerprint", "credentials", ["token_fingerprint"], unique=True
    )
    op.create_index(
        "idx_credential_allocation", "credentials", ["allocation_id"], unique=False
    )


def downgrade() -> None:
    """Collapse back to one credential per allocation (keeps the newest active
    per allocation). Lossy — extra per-device credentials are dropped."""
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT allocation_id, token_fingerprint, token_prefix, created_at "
            "FROM credentials WHERE revoked_at IS NULL ORDER BY created_at ASC"
        )
    ).mappings().all()
    # Keep one row per allocation (last wins → newest active credential).
    keep: dict[str, dict[str, object]] = {}
    for row in rows:
        keep[row["allocation_id"]] = dict(row)

    op.drop_index("idx_credential_allocation", table_name="credentials")
    op.drop_index("idx_credential_fingerprint", table_name="credentials")
    op.create_table(
        "credentials_old",
        sa.Column("allocation_id", sa.String(length=26), nullable=False),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["allocation_id"], ["allocations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("allocation_id"),
        sa.UniqueConstraint("token_fingerprint"),
    )
    if keep:
        op.bulk_insert(
            sa.table(
                "credentials_old",
                sa.column("allocation_id"),
                sa.column("token_fingerprint"),
                sa.column("token_prefix"),
                sa.column("created_at"),
            ),
            [
                {
                    "allocation_id": r["allocation_id"],
                    "token_fingerprint": r["token_fingerprint"],
                    "token_prefix": r["token_prefix"],
                    "created_at": r["created_at"],
                }
                for r in keep.values()
            ],
        )
    op.drop_table("credentials")
    op.rename_table("credentials_old", "credentials")
    op.create_index(
        "idx_credential_fingerprint", "credentials", ["token_fingerprint"], unique=True
    )
