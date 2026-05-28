"""Phase 11 T038: StoredResponseService store / resolve / TTL cleanup."""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai_api.db import Base
from ai_api.models import StoredResponse
from ai_api.services.stored_responses import StoredResponseService

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'sr.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_store_and_resolve_own(session: AsyncSession) -> None:
    svc = StoredResponseService(session)
    rid = await svc.store(allocation_id="A", provider="azure", upstream_response_id="resp_1")
    await session.commit()
    assert rid == "resp_1"
    assert await svc.resolve_for_continuation(
        response_id="resp_1", allocation_id="A", provider="azure"
    ) == "resp_1"


@pytest.mark.asyncio
async def test_resolve_forbidden_other_allocation(session: AsyncSession) -> None:
    svc = StoredResponseService(session)
    await svc.store(allocation_id="A", provider="azure", upstream_response_id="resp_1")
    await session.commit()
    assert await svc.resolve_for_continuation(
        response_id="resp_1", allocation_id="B", provider="azure"
    ) == "forbidden"


@pytest.mark.asyncio
async def test_resolve_not_found_and_expired(session: AsyncSession) -> None:
    svc = StoredResponseService(session)
    assert await svc.resolve_for_continuation(
        response_id="ghost", allocation_id="A", provider="azure"
    ) == "not_found"
    # expired row
    now = datetime.now(UTC)
    session.add(StoredResponse(
        response_id="old", allocation_id="A", provider="azure",
        upstream_response_id="old", created_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=1),
    ))
    await session.commit()
    assert await svc.resolve_for_continuation(
        response_id="old", allocation_id="A", provider="azure"
    ) == "not_found"


@pytest.mark.asyncio
async def test_cleanup_expired(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    session.add(StoredResponse(
        response_id="exp", allocation_id="A", provider="azure", upstream_response_id="exp",
        created_at=now - timedelta(days=40), expires_at=now - timedelta(days=1),
    ))
    session.add(StoredResponse(
        response_id="live", allocation_id="A", provider="azure", upstream_response_id="live",
        created_at=now, expires_at=now + timedelta(days=1),
    ))
    await session.commit()
    removed = await StoredResponseService(session).cleanup_expired()
    await session.commit()
    assert removed == 1
    assert await session.get(StoredResponse, "exp") is None
    assert await session.get(StoredResponse, "live") is not None
