"""Integration test fixtures: real Postgres via testcontainers (or skip if Docker not available)."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_api.config import get_settings
from ai_api.db import Base, dispose_engine, get_engine, reset_engine_for_testing
from ai_api.main import create_app


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Provide a Postgres URL. Use existing AIAPI_TEST_PG_URL if set, else testcontainers."""
    explicit = os.environ.get("AIAPI_TEST_PG_URL")
    if explicit:
        yield explicit
        return
    try:
        from testcontainers.postgres import PostgresContainer
    except Exception as e:
        pytest.skip(f"testcontainers not available: {e}")

    with PostgresContainer("postgres:15-alpine", driver="asyncpg") as pg:
        url = pg.get_connection_url()
        # testcontainers returns postgresql+psycopg2 by default; with driver= override -> asyncpg
        yield url


@pytest_asyncio.fixture
async def app_client(postgres_url: str) -> AsyncIterator[AsyncClient]:
    get_settings.cache_clear()
    os.environ["DATABASE_URL"] = postgres_url
    reset_engine_for_testing(postgres_url)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await dispose_engine()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


@pytest.fixture
def azure_key() -> str:
    return os.environ["AZURE_OPENAI_API_KEY"]
