"""Phase 017 US1: first-admin provisioning CLI (`ai_api.cli.create_admin`).

Exercises the testable core `provision()` against real DB rows on a temp-file
SQLite, plus the exit-code mapping. No subprocess / no Docker needed.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai_api.cli.create_admin import ProvisionResult, provision, result_to_exit_code
from ai_api.db import Base
from ai_api.models import Member, MemberProvider, MemberStatus
from ai_api.services.members import MemberService

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def sm(tmp_path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    db_path = tmp_path / "bootstrap.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _get(sm: async_sessionmaker[AsyncSession], email: str) -> Member | None:
    async with sm() as s:
        return await MemberService(s).get_by_email(email)


# T003 — clean DB, OIDC provisioning
@pytest.mark.asyncio
async def test_provision_oidc_on_clean_db(sm) -> None:
    async with sm() as s:
        res = await provision(s, email="Admin@Org.edu", provider="google_oidc")
        await s.commit()
    assert res.status == "created"
    m = await _get(sm, "admin@org.edu")
    assert m is not None
    assert m.is_admin is True
    assert m.provider == MemberProvider.google_oidc
    assert m.password_hash is None
    assert m.status == MemberStatus.active


# T004 — idempotent rerun
@pytest.mark.asyncio
async def test_provision_is_idempotent(sm) -> None:
    async with sm() as s:
        await provision(s, email="admin@org.edu", provider="google_oidc")
        await s.commit()
    async with sm() as s:
        res2 = await provision(s, email="admin@org.edu", provider="google_oidc")
        await s.commit()
    assert res2.status == "unchanged"
    assert result_to_exit_code(res2) == 0
    # exactly one row
    async with sm() as s:
        from sqlalchemy import func, select

        n = await s.scalar(select(func.count()).select_from(Member))
    assert n == 1


# T005 — existing email with conflicting provider
@pytest.mark.asyncio
async def test_provision_provider_conflict_refuses(sm) -> None:
    async with sm() as s:
        await MemberService(s).create(
            email="admin@org.edu",
            provider=MemberProvider.local_password,
            initial_password="VerySafePass123",
        )
        await s.commit()
    async with sm() as s:
        res = await provision(s, email="admin@org.edu", provider="google_oidc")
        await s.commit()
    assert res.status == "conflict"
    assert result_to_exit_code(res) != 0
    # existing member untouched: still local_password, still not admin
    m = await _get(sm, "admin@org.edu")
    assert m is not None
    assert m.provider == MemberProvider.local_password
    assert m.is_admin is False


# T006 — local_password provisioning issues an invitation
@pytest.mark.asyncio
async def test_provision_local_password_issues_invitation(sm) -> None:
    async with sm() as s:
        res = await provision(s, email="pwadmin@org.edu", provider="local_password")
        await s.commit()
    assert res.status == "created"
    assert res.invitation, "local_password provisioning must return a one-time invitation"
    m = await _get(sm, "pwadmin@org.edu")
    assert m is not None
    assert m.is_admin is True
    assert m.provider == MemberProvider.local_password


# T007a — other admin already exists, target email absent → still create+promote
@pytest.mark.asyncio
async def test_provision_creates_even_when_other_admin_exists(sm) -> None:
    async with sm() as s:
        first = await provision(s, email="first@org.edu", provider="google_oidc")
        await s.commit()
    assert first.status == "created"
    async with sm() as s:
        res = await provision(s, email="second@org.edu", provider="google_oidc")
        await s.commit()
    assert res.status == "created"
    m = await _get(sm, "second@org.edu")
    assert m is not None and m.is_admin is True


# T007b — existing member, provider matches, not yet admin → promoted
@pytest.mark.asyncio
async def test_provision_promotes_existing_non_admin(sm) -> None:
    async with sm() as s:
        await MemberService(s).create(
            email="member@org.edu",
            provider=MemberProvider.google_oidc,
            send_invitation=False,
        )
        await s.commit()
    async with sm() as s:
        res = await provision(s, email="member@org.edu", provider="google_oidc")
        await s.commit()
    assert res.status == "promoted"
    assert result_to_exit_code(res) == 0
    m = await _get(sm, "member@org.edu")
    assert m is not None and m.is_admin is True


def test_result_to_exit_code_mapping() -> None:
    assert result_to_exit_code(ProvisionResult(status="created", email="a", member_id="1")) == 0
    assert result_to_exit_code(ProvisionResult(status="promoted", email="a", member_id="1")) == 0
    assert result_to_exit_code(ProvisionResult(status="unchanged", email="a", member_id="1")) == 0
    assert result_to_exit_code(ProvisionResult(status="conflict", email="a", member_id="1")) != 0
