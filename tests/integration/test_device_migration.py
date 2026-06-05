"""Phase 19 Foundational integration test (Postgres): migration 0016 adds the
`device_authorizations` table and does not regress existing tokens.

Drives real Alembic (the test DB normally builds schema via metadata.create_all),
then asserts the new table exists and an existing token still resolves. Skipped
when no Postgres/Docker is available (mirrors the other integration tests).
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from ulid import ULID

from ai_api.config import get_settings
from ai_api.models import (
    Allocation,
    AllocationOrigin,
    AllocationStatus,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.allocations import AllocationService
from ai_api.services.credentials import generate_token


def _alembic_config(url: str):
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    return Config(os.path.join(root, "alembic.ini"))


def test_migration_0016_adds_device_table_no_regression(postgres_url: str) -> None:
    from alembic import command

    member_id = str(ULID())
    alloc_id = str(ULID())
    token = generate_token()

    async def wipe() -> None:
        engine = create_async_engine(postgres_url, poolclass=None)
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    async def seed_existing_token() -> None:
        engine = create_async_engine(postgres_url)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(UTC)
        async with sm() as s:
            s.add(
                Member(
                    id=member_id,
                    email="legacy@example.com",
                    provider=MemberProvider.external,
                    display_name="legacy",
                    status=MemberStatus.active,
                    password_hash=None,
                    created_at=now,
                    disabled_at=None,
                    created_by="test",
                )
            )
            s.add(
                Allocation(
                    id=alloc_id,
                    member_id=member_id,
                    subject_snapshot="legacy@example.com",
                    resource_model="azure/gpt-test",
                    status=AllocationStatus.active,
                    created_at=now,
                    revoked_at=None,
                    created_by="test",
                    note=None,
                    quota_tokens_per_month=None,
                    origin=AllocationOrigin.admin,
                )
            )
            await s.flush()
            # Insert a credential directly (Phase 20 head schema: member-owned key
            # scoped to one allocation via credential_allocations).
            cred_id = str(ULID())
            await s.execute(
                text(
                    "INSERT INTO credentials "
                    "(id, member_id, name, token_fingerprint, token_prefix, created_at) "
                    "VALUES (:id, :m, :n, :f, :p, :c)"
                ),
                {
                    "id": cred_id,
                    "m": member_id,
                    "n": "預設",
                    "f": token.fingerprint,
                    "p": token.prefix,
                    "c": now,
                },
            )
            await s.execute(
                text(
                    "INSERT INTO credential_allocations "
                    "(credential_id, allocation_id, resource_model) "
                    "VALUES (:cid, :a, :rm)"
                ),
                {"cid": cred_id, "a": alloc_id, "rm": "azure/gpt-test"},
            )
            await s.commit()
        await engine.dispose()

    async def assert_after() -> None:
        engine = create_async_engine(postgres_url)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert "device_authorizations" in tables
            cols = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("device_authorizations")}
            )
            assert {"device_code", "user_code", "status", "encrypted_token", "expires_at"} <= cols
        async with sm() as s:
            alloc = await AllocationService(s).lookup_by_token(token.plaintext)
            assert alloc is not None and alloc.id == alloc_id  # existing token still works
        await engine.dispose()

    try:
        asyncio.run(wipe())
        command.upgrade(_alembic_config(postgres_url), "head")
        asyncio.run(seed_existing_token())
        asyncio.run(assert_after())
    finally:
        # Leave a clean schema so metadata-based app_client tests aren't polluted.
        asyncio.run(wipe())
        get_settings.cache_clear()
