"""Phase 018 (Foundational): aggregate_usage member-scope filter.

Docker-free — uses its own temp-file SQLite engine (Docker/testcontainers not
required). Verifies that passing member_id scopes the aggregate strictly to that
member, that omitting it preserves existing behaviour, and that only successful
calls are counted.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ulid import ULID

from ai_api.db import Base
from ai_api.models import (
    Allocation,
    AllocationOrigin,
    AllocationStatus,
    CallOutcome,
    CallRecord,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.usage import aggregate_usage

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)
FROM = NOW - timedelta(days=7)
TO = NOW + timedelta(days=1)


@pytest_asyncio.fixture
async def sm(tmp_path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _member(s: AsyncSession, email: str) -> str:
    m = Member(
        id=str(ULID()), email=email, provider=MemberProvider.external,
        external_id=email, display_name=email, status=MemberStatus.active,
        password_hash=None, created_at=NOW, disabled_at=None, created_by="test",
    )
    s.add(m)
    await s.flush()
    return m.id


async def _alloc(s: AsyncSession, member_id: str, model: str) -> str:
    a = Allocation(
        id=str(ULID()), member_id=member_id, subject_snapshot=model,
        resource_model=model, status=AllocationStatus.active, created_at=NOW,
        revoked_at=None, created_by="test", note=None, quota_tokens_per_month=None,
        is_service_allocation=False, quota_locked=False, origin=AllocationOrigin.admin,
    )
    s.add(a)
    await s.flush()
    return a.id


async def _call(
    s: AsyncSession, alloc_id: str, model: str, *,
    total: int, cost: float | None, outcome: CallOutcome = CallOutcome.success,
) -> None:
    s.add(CallRecord(
        id=str(ULID()), request_id=str(ULID()), allocation_id=alloc_id,
        subject=model, model=model, started_at=NOW, finished_at=NOW,
        status_code=200, outcome=outcome,
        prompt_tokens=total // 2, completion_tokens=total - total // 2,
        total_tokens=total, cost_usd=cost, error_message=None,
    ))


# T002 — member_id scopes strictly; A excludes B
@pytest.mark.asyncio
async def test_member_id_scopes_strictly(sm) -> None:
    async with sm() as s:
        a = await _member(s, "a@x.com")
        b = await _member(s, "b@x.com")
        aa = await _alloc(s, a, "azure/m")
        ba = await _alloc(s, b, "azure/m")
        await _call(s, aa, "azure/m", total=100, cost=1.0)
        await _call(s, ba, "azure/m", total=999, cost=9.0)
        await s.commit()
        rows_a = await aggregate_usage(s, group_by="member", from_=FROM, to=TO, member_id=a)
    assert len(rows_a) == 1
    assert rows_a[0].total_tokens == 100  # only A's call, not B's 999
    assert rows_a[0].group_key == a


# T003 — all three group_by honour member_id; omitting it is unchanged
@pytest.mark.asyncio
async def test_group_by_branches_honour_member_id(sm) -> None:
    async with sm() as s:
        a = await _member(s, "a@x.com")
        b = await _member(s, "b@x.com")
        aa = await _alloc(s, a, "azure/m1")
        ba = await _alloc(s, b, "azure/m2")
        await _call(s, aa, "azure/m1", total=100, cost=1.0)
        await _call(s, ba, "azure/m2", total=200, cost=2.0)
        await s.commit()
        by_model = await aggregate_usage(s, group_by="model", from_=FROM, to=TO, member_id=a)
        by_alloc = await aggregate_usage(s, group_by="allocation", from_=FROM, to=TO, member_id=a)
        all_models = await aggregate_usage(s, group_by="model", from_=FROM, to=TO)
    assert {r.group_key for r in by_model} == {"azure/m1"}  # only A's model
    assert {r.group_key for r in by_alloc} == {aa}
    # omitting member_id keeps existing behaviour: both members' models present
    assert {r.group_key for r in all_models} == {"azure/m1", "azure/m2"}


# T004 — only successful calls counted
@pytest.mark.asyncio
async def test_only_success_counted(sm) -> None:
    async with sm() as s:
        a = await _member(s, "a@x.com")
        aa = await _alloc(s, a, "azure/m")
        await _call(s, aa, "azure/m", total=100, cost=1.0, outcome=CallOutcome.success)
        await _call(s, aa, "azure/m", total=500, cost=5.0, outcome=CallOutcome.upstream_error)
        await s.commit()
        rows = await aggregate_usage(s, group_by="member", from_=FROM, to=TO, member_id=a)
    assert rows[0].total_tokens == 100  # failed 500 excluded
    assert rows[0].call_count == 1
