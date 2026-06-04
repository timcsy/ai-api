"""Phase 18 Foundational integration tests (Postgres).

T002 — migration 0015 preserves existing tokens (zero-regression): seed the
*old* single-credential schema (allocation_id as PK), run ``alembic upgrade
head``, and assert the old token still resolves and the row gained a ``預設``
credential.

T003 — multi-credential lookup + per-credential revoke: many credentials on one
allocation each resolve to it; soft-revoking one excludes only that one.

Both require Postgres (the PK change is the whole point) and are skipped when no
Postgres/Docker is available, mirroring the other integration tests.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from ulid import ULID

from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
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

_PRE_0015 = "0014_admin_notifications"


def _alembic_config(url: str):
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()  # env.py reads settings.database_url at import
    return Config(os.path.join(root, "alembic.ini"))


def test_migration_0015_preserves_existing_token(postgres_url: str) -> None:
    """Old-schema single credential survives the 1:1 → 1:N migration verbatim."""
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

    async def seed_old() -> None:
        # members/allocations are unchanged by 0015 → ORM is safe; the credential
        # must be inserted raw because at 0014 the table still has the old columns.
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
            await s.execute(
                text(
                    "INSERT INTO credentials "
                    "(allocation_id, token_fingerprint, token_prefix, created_at) "
                    "VALUES (:a, :f, :p, :c)"
                ),
                {
                    "a": alloc_id,
                    "f": token.fingerprint,
                    "p": token.prefix,
                    "c": now,
                },
            )
            await s.commit()
        await engine.dispose()

    async def assert_after() -> None:
        engine = create_async_engine(postgres_url)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            svc = AllocationService(s)
            alloc = await svc.lookup_by_token(token.plaintext)
            assert alloc is not None, "existing token must still resolve after 0015"
            assert alloc.id == alloc_id
            creds = list(await svc.list_credentials(alloc_id))
            assert len(creds) == 1
            assert creds[0].name == "預設"
            assert creds[0].token_fingerprint == token.fingerprint
            assert creds[0].token_prefix == token.prefix
            assert creds[0].revoked_at is None
        await engine.dispose()

    try:
        asyncio.run(wipe())
        command.upgrade(_alembic_config(postgres_url), _PRE_0015)
        asyncio.run(seed_old())
        command.upgrade(_alembic_config(postgres_url), "head")
        asyncio.run(assert_after())
    finally:
        # Leave a clean schema so the metadata-based app_client fixture (used by
        # other integration tests) can drop_all/create_all without tripping over
        # Alembic-named constraints.
        asyncio.run(wipe())
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_multi_credential_lookup_and_revoke(
    app_client: AsyncClient,  # builds the (new) schema + resets the engine
) -> None:
    """Many credentials on one allocation each resolve; revoking one is isolated."""
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        member = Member(
            id=str(ULID()),
            email="multi@example.com",
            provider=MemberProvider.external,
            display_name="multi",
            status=MemberStatus.active,
            password_hash=None,
            created_at=now,
            disabled_at=None,
            created_by="test",
        )
        s.add(member)
        await s.flush()
        svc = AllocationService(s)
        created = await svc.create(
            member_id=member.id, resource_model="azure/gpt-test"
        )
        alloc = created.allocation
        default_token = created.token  # the "預設" credential
        cred_b, token_b = await svc.add_credential(alloc, name="筆電")
        _cred_c, token_c = await svc.add_credential(alloc, name="桌機")
        await s.commit()
        alloc_id = alloc.id

    # All three resolve to the same allocation.
    async with sm() as s:
        svc = AllocationService(s)
        for tok in (default_token, token_b, token_c):
            found = await svc.lookup_by_token(tok.plaintext)
            assert found is not None and found.id == alloc_id
        await s.commit()

    # Revoke B only.
    async with sm() as s:
        svc = AllocationService(s)
        revoked = await svc.revoke_credential(cred_b.id)
        assert revoked is not None and revoked.revoked_at is not None
        await s.commit()

    # B no longer resolves; the others still do (no collateral revoke).
    async with sm() as s:
        svc = AllocationService(s)
        assert await svc.lookup_by_token(token_b.plaintext) is None
        assert (await svc.lookup_by_token(default_token.plaintext)) is not None
        c_found = await svc.lookup_by_token(token_c.plaintext)
        assert c_found is not None and c_found.id == alloc_id
        creds = list(await svc.list_credentials(alloc_id))
        assert len(creds) == 3  # revoked rows are still listed
        assert {c.name for c in creds} == {"預設", "筆電", "桌機"}
        assert sum(1 for c in creds if c.revoked_at is None) == 2
