"""Phase 25: /v1/responses gate truth source is responses_support.lookup (axis ③).
Was Phase 11's static model_supports_responses; the soft gate now only pre-blocks
on a manual "unavailable" (responses:blocked)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai_api.db import Base
from ai_api.models import ModelCatalog
from ai_api.services import responses_support as rs

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'c.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


def _catalog(slug: str, caps: list[str]) -> ModelCatalog:
    now = datetime.now(UTC)
    return ModelCatalog(
        slug=slug, provider="azure", display_name=slug, family="f", description="d",
        modality_input=["text"], modality_output=["text"], capabilities=caps,
        context_window=1000, cost_tier="low", recommended_for=[], tags=[],
        example_request={}, created_at=now, updated_at=now,
    )


@pytest.mark.asyncio
async def test_available_when_responses_marker(session: AsyncSession) -> None:
    session.add(_catalog("azure/gpt-5", [rs.RESPONSES, "chat"]))
    await session.commit()
    assert (await rs.lookup(session, "azure/gpt-5"))["state"] == "available"


@pytest.mark.asyncio
async def test_unknown_when_no_marker(session: AsyncSession) -> None:
    session.add(_catalog("azure/gpt-4o", ["chat"]))
    await session.commit()
    assert (await rs.lookup(session, "azure/gpt-4o"))["state"] == "unknown"


@pytest.mark.asyncio
async def test_unavailable_when_blocked(session: AsyncSession) -> None:
    session.add(_catalog("azure/blocked", ["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL]))
    await session.commit()
    assert (await rs.lookup(session, "azure/blocked"))["state"] == "unavailable"


@pytest.mark.asyncio
async def test_unknown_model_is_unknown(session: AsyncSession) -> None:
    assert (await rs.lookup(session, "azure/ghost"))["state"] == "unknown"
