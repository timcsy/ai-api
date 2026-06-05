"""Phase 20: scoped application credentials — credentials 1:N → M:N.

A credential becomes a member-owned application key whose scope is a SET of the
member's allocations:
* `credentials` loses `allocation_id`, gains `member_id`;
* new association `credential_allocations(credential_id, allocation_id,
  resource_model)` with `UNIQUE(credential_id, resource_model)`.

In-place ALTER (NOT drop+rename): `device_authorizations.credential_id`
(Phase 19) references `credentials`, so the table is altered in place via
batch_alter_table (SQLite rebuild / Postgres native ALTER).

Existing rows: each credential gets `member_id` (from its old allocation's
member) + one `credential_allocations` row (its old allocation + that
allocation's resource_model) → existing tokens keep working unchanged
(scope-of-one is the 1:N special case).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_scoped_credentials"
down_revision: str | Sequence[str] | None = "0016_device_authorizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. New association table.
    op.create_table(
        "credential_allocations",
        sa.Column("credential_id", sa.String(length=26), nullable=False),
        sa.Column("allocation_id", sa.String(length=26), nullable=False),
        sa.Column("resource_model", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["allocation_id"], ["allocations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("credential_id", "allocation_id"),
        sa.UniqueConstraint("credential_id", "resource_model", name="uq_credential_model"),
    )
    op.create_index(
        "idx_credalloc_allocation", "credential_allocations", ["allocation_id"], unique=False
    )

    # 2. Backfill scope from the existing 1:1 link (old allocation_id still present).
    op.execute(
        sa.text(
            "INSERT INTO credential_allocations (credential_id, allocation_id, resource_model) "
            "SELECT c.id, c.allocation_id, a.resource_model "
            "FROM credentials c JOIN allocations a ON a.id = c.allocation_id"
        )
    )

    # 3. Add member_id (nullable), backfill from the old allocation's member.
    with op.batch_alter_table("credentials") as batch:
        batch.add_column(sa.Column("member_id", sa.String(length=26), nullable=True))
    op.execute(
        sa.text(
            "UPDATE credentials SET member_id = "
            "(SELECT a.member_id FROM allocations a WHERE a.id = credentials.allocation_id)"
        )
    )

    # 4. member_id NOT NULL + FK/index; drop the old allocation_id column/index/FK.
    with op.batch_alter_table("credentials") as batch:
        batch.alter_column("member_id", existing_type=sa.String(length=26), nullable=False)
        batch.drop_index("idx_credential_allocation")
        batch.create_index("idx_credential_member", ["member_id"], unique=False)
        batch.create_foreign_key(
            "fk_credential_member", "members", ["member_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("allocation_id")


def downgrade() -> None:
    # Lossy: collapse each credential back to a single allocation (its first scope
    # row); drop the association table. Multi-allocation keys lose extra scope.
    with op.batch_alter_table("credentials") as batch:
        batch.add_column(sa.Column("allocation_id", sa.String(length=26), nullable=True))
    op.execute(
        sa.text(
            "UPDATE credentials SET allocation_id = "
            "(SELECT ca.allocation_id FROM credential_allocations ca "
            "WHERE ca.credential_id = credentials.id LIMIT 1)"
        )
    )
    with op.batch_alter_table("credentials") as batch:
        batch.alter_column("allocation_id", existing_type=sa.String(length=26), nullable=False)
        batch.drop_constraint("fk_credential_member", type_="foreignkey")
        batch.drop_index("idx_credential_member")
        batch.create_index("idx_credential_allocation", ["allocation_id"], unique=False)
        batch.create_foreign_key(
            "fk_credential_allocation", "allocations", ["allocation_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("member_id")
    op.drop_index("idx_credalloc_allocation", table_name="credential_allocations")
    op.drop_table("credential_allocations")
