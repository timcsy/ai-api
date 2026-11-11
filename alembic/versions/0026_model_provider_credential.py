"""Pin a catalog model to one provider credential (resource-specific routing).

Additive, nullable column (zero regression):
  model_catalog: provider_credential_id (NULL ⇒ round-robin across the
  provider's active credentials, the pre-existing behaviour).

Motivation: with two `azure` credentials pointing at different Azure resources
(different deployments), round-robin routes a model to a resource that lacks its
deployment ~half the time → 404 DeploymentNotFound. Pinning routes it to the one
resource that actually hosts it.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_model_provider_credential"
down_revision: str | Sequence[str] | None = "0025_oauth_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_catalog",
        sa.Column("provider_credential_id", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_catalog", "provider_credential_id")
