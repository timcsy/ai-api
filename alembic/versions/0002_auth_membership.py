"""auth_membership

Add Member, Session, EmailWhitelist, AutoRegisterRule, SourceRestriction,
InvitationToken, PasswordAttempt, AuthAuditLog, OidcState tables.
Upgrade Allocation: add member_id (FK), subject_snapshot; data-migrate from
the old `subject` string; drop `subject`.

Revision ID: 0002_auth_membership
Revises: 9f4326e504c4
Create Date: 2026-05-22 00:00:00.000000
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from ulid import ULID

from alembic import op

revision: str = "0002_auth_membership"
down_revision: str | Sequence[str] | None = "9f4326e504c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- new tables ---
    op.create_table(
        "members",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "google_oidc",
                "local_password",
                "external",
                name="memberprovider",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "disabled", name="memberstatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
    )
    op.create_index("idx_member_email", "members", ["email"], unique=True)
    op.create_index("idx_member_provider_external", "members", ["provider", "external_id"])
    op.create_index("idx_member_status", "members", ["status"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "member_id",
            sa.String(length=26),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "revoked", name="sessionstatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=128), nullable=True),
    )
    op.create_index("idx_session_member_time", "sessions", ["member_id", "last_seen_at"])
    op.create_index("idx_session_status", "sessions", ["status"])

    op.create_table(
        "email_whitelist",
        sa.Column("email", sa.String(length=320), primary_key=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("added_by", sa.String(length=128), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "auto_register_rules",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "rule_type",
            sa.Enum("email_domain", name="ruletype", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("pattern", sa.String(length=256), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
    )
    op.create_index("idx_rule_enabled", "auto_register_rules", ["enabled", "rule_type"])

    op.create_table(
        "source_restrictions",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("idx_source_restriction_enabled", "source_restrictions", ["enabled"])

    op.create_table(
        "invitation_tokens",
        sa.Column("token_fingerprint", sa.String(length=64), primary_key=True),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column(
            "member_id",
            sa.String(length=26),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
    )
    op.create_index("idx_invitation_member", "invitation_tokens", ["member_id"])
    op.create_index("idx_invitation_expires", "invitation_tokens", ["expires_at"])

    op.create_table(
        "password_attempts",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "success",
                "bad_password",
                "unknown_email",
                "locked",
                "disabled",
                name="attemptoutcome",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
    )
    op.create_index("idx_attempt_email_time", "password_attempts", ["email", "attempted_at"])

    op.create_table(
        "auth_audit_log",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "login_success",
                "login_failure",
                "logout",
                "member_created",
                "member_disabled",
                "member_deleted",
                "whitelist_added",
                "whitelist_removed",
                "rule_added",
                "rule_removed",
                "restriction_added",
                "restriction_removed",
                "password_changed",
                "invitation_issued",
                "invitation_used",
                name="auditeventtype",
                native_enum=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            sa.Enum(
                "admin",
                "member",
                "system",
                "anonymous",
                name="actortype",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("redacted_message", sa.Text(), nullable=True),
    )
    op.create_index("idx_audit_actor_time", "auth_audit_log", ["actor_type", "actor_id", "created_at"])
    op.create_index("idx_audit_target_time", "auth_audit_log", ["target_type", "target_id", "created_at"])
    op.create_index("idx_audit_event_time", "auth_audit_log", ["event_type", "created_at"])

    op.create_table(
        "oidc_states",
        sa.Column("state", sa.String(length=128), primary_key=True),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("redirect_to", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_oidc_state_expires", "oidc_states", ["expires_at"])

    # --- upgrade allocations ---
    op.add_column("allocations", sa.Column("member_id", sa.String(length=26), nullable=True))
    op.add_column("allocations", sa.Column("subject_snapshot", sa.String(length=256), nullable=True))

    # --- data migration: distinct subject -> Member(external) ---
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT DISTINCT subject FROM allocations")).all()
    now = datetime.now(UTC)
    subject_to_member: dict[str, str] = {}
    for (subject,) in rows:
        if subject is None:
            continue
        member_id = str(ULID())
        subject_to_member[subject] = member_id
        connection.execute(
            sa.text(
                "INSERT INTO members (id, email, provider, external_id, display_name, "
                "status, password_hash, created_at, disabled_at, created_by) "
                "VALUES (:id, :email, :provider, :external_id, :display_name, "
                ":status, NULL, :created_at, NULL, :created_by)"
            ),
            {
                "id": member_id,
                "email": subject.lower(),
                "provider": "external",
                "external_id": subject,
                "display_name": subject,
                "status": "active",
                "created_at": now,
                "created_by": "migration_0002",
            },
        )

    for subject, member_id in subject_to_member.items():
        connection.execute(
            sa.text(
                "UPDATE allocations SET member_id = :mid, subject_snapshot = :s "
                "WHERE subject = :s2"
            ),
            {"mid": member_id, "s": subject, "s2": subject},
        )

    # --- finalise: NOT NULL + FK + drop subject ---
    # SQLite cannot ALTER constraints, so use batch mode.
    with op.batch_alter_table("allocations") as batch:
        batch.alter_column("member_id", existing_type=sa.String(length=26), nullable=False)
        batch.alter_column(
            "subject_snapshot",
            existing_type=sa.String(length=256),
            nullable=False,
        )
        batch.create_foreign_key(
            "fk_allocations_member",
            "members",
            ["member_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        # Drop the index BEFORE the column it covers. On Postgres (in-place
        # ALTER) dropping `subject` auto-drops its dependent index, so a later
        # explicit drop_index fails "does not exist". SQLite (batch table-copy)
        # tolerated the reverse order, which is why this only bit on Postgres.
        batch.drop_index("idx_allocation_subject")
        batch.drop_column("subject")
        batch.create_index("idx_allocation_member", ["member_id", "created_at"])


def downgrade() -> None:
    with op.batch_alter_table("allocations") as batch:
        batch.add_column(sa.Column("subject", sa.String(length=256), nullable=True))
        batch.drop_index("idx_allocation_member")
        batch.create_index("idx_allocation_subject", ["subject", "created_at"])
        batch.drop_constraint("fk_allocations_member", type_="foreignkey")

    connection = op.get_bind()
    connection.execute(sa.text("UPDATE allocations SET subject = subject_snapshot"))

    with op.batch_alter_table("allocations") as batch:
        batch.alter_column("subject", existing_type=sa.String(length=256), nullable=False)
        batch.drop_column("member_id")
        batch.drop_column("subject_snapshot")

    op.drop_table("oidc_states")
    op.drop_table("auth_audit_log")
    op.drop_table("password_attempts")
    op.drop_table("invitation_tokens")
    op.drop_table("source_restrictions")
    op.drop_table("auto_register_rules")
    op.drop_table("email_whitelist")
    op.drop_table("sessions")
    op.drop_table("members")
