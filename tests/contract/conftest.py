"""Contract test fixtures: spin up the app against an in-memory SQLite."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from httpx import ASGITransport, AsyncClient

from ai_api.config import get_settings
from ai_api.db import Base, dispose_engine, get_engine, reset_engine_for_testing
from ai_api.main import create_app

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "specs" / "001-gateway-core" / "contracts"


@pytest.fixture(scope="session")
def openapi_spec() -> dict:
    with (CONTRACT_DIR / "openapi.yaml").open() as f:
        return yaml.safe_load(f)


@pytest_asyncio.fixture
async def app_client() -> AsyncIterator[AsyncClient]:
    get_settings.cache_clear()
    reset_engine_for_testing("sqlite+aiosqlite:///:memory:")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await dispose_engine()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


@pytest_asyncio.fixture
async def member_id() -> str:
    """Return id of a freshly-created external Member (single use per test)."""
    from ai_api.db import get_sessionmaker
    from tests._helpers import create_external_member

    sm = get_sessionmaker()
    async with sm() as s:
        return await create_external_member(s, "alice@example.com")


@pytest_asyncio.fixture
async def make_member():
    """Return a coroutine factory that creates Members on demand."""
    from ai_api.db import get_sessionmaker
    from tests._helpers import create_external_member

    sm = get_sessionmaker()

    async def _make(email: str) -> str:
        async with sm() as s:
            return await create_external_member(s, email)

    return _make
