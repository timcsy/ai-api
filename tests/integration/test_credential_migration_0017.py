"""Phase 20 Foundational integration test (Postgres): migration 0017
(credentials 1:N → M:N) preserves existing single-allocation tokens.

Seeds an old-style credential (with `allocation_id`) at revision 0016, runs
`alembic upgrade head` (0017), and asserts the token still resolves to the same
allocation, a `credential_allocations` scope row was created, `member_id` was
backfilled, and the old `allocation_id` column is gone. Skipped without Postgres.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from ulid import ULID

from ai_api.config import get_settings
from ai_api.services.allocations import AllocationService
from ai_api.services.credentials import generate_token

_PRE = "0016_device_authorizations"


def _cfg(url: str):
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    return Config(os.path.join(root, "alembic.ini"))


def test_migration_0017_preserves_single_allocation_token(postgres_url: str) -> None:
    from alembic import command

    member_id = str(ULID())
    alloc_id = str(ULID())
    cred_id = str(ULID())
    token = generate_token()

    async def wipe() -> None:
        engine = create_async_engine(postgres_url, poolclass=None)
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    async def seed_old() -> None:
        # At revision 0016 credentials still has allocation_id (1:N). Insert raw.
        engine = create_async_engine(postgres_url)
        now = datetime.now(UTC)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO members (id, email, provider, display_name, status, "
                    "password_hash, created_at, disabled_at, created_by) VALUES "
                    "(:id, :em, 'external', 'legacy', 'active', NULL, :c, NULL, 'test')"
                ),
                {"id": member_id, "em": "legacy@example.com", "c": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO allocations (id, member_id, subject_snapshot, resource_model, "
                    "status, created_at, revoked_at, created_by, note, quota_tokens_per_month, "
                    "is_service_allocation, quota_locked, origin) VALUES "
                    "(:id, :m, :ss, :rm, 'active', :c, NULL, 'test', NULL, NULL, false, false, 'admin')"
                ),
                {"id": alloc_id, "m": member_id, "ss": "legacy@example.com", "rm": "azure/gpt-test", "c": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO credentials (id, allocation_id, name, token_fingerprint, "
                    "token_prefix, created_at) VALUES (:id, :a, '預設', :f, :p, :c)"
                ),
                {"id": cred_id, "a": alloc_id, "f": token.fingerprint, "p": token.prefix, "c": now},
            )
        await engine.dispose()

    async def assert_after() -> None:
        engine = create_async_engine(postgres_url)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.connect() as conn:
            cred_cols = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("credentials")}
            )
            assert "member_id" in cred_cols
            assert "allocation_id" not in cred_cols  # dropped
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert "credential_allocations" in tables
            # device_authorizations FK to credentials still present (Phase 19).
            assert "device_authorizations" in tables
            scope = (
                await conn.execute(
                    text(
                        "SELECT allocation_id, resource_model FROM credential_allocations "
                        "WHERE credential_id = :cid"
                    ),
                    {"cid": cred_id},
                )
            ).all()
            assert scope == [(alloc_id, "azure/gpt-test")]  # scope-of-one backfilled
            mem = (
                await conn.execute(
                    text("SELECT member_id FROM credentials WHERE id = :cid"), {"cid": cred_id}
                )
            ).scalar_one()
            assert mem == member_id  # member_id backfilled
        async with sm() as s:
            svc = AllocationService(s)
            cred = await svc.lookup_credential_by_token(token.plaintext)
            assert cred is not None  # existing token still resolves
            alloc = await svc.resolve_scope_allocation(cred, "azure/gpt-test")
            assert alloc is not None and alloc.id == alloc_id  # still bills same allocation
        await engine.dispose()

    try:
        asyncio.run(wipe())
        command.upgrade(_cfg(postgres_url), _PRE)
        asyncio.run(seed_old())
        command.upgrade(_cfg(postgres_url), "head")
        asyncio.run(assert_after())
    finally:
        asyncio.run(wipe())
        get_settings.cache_clear()
