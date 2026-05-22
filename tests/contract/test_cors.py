"""Contract tests for CORS allowlist behaviour (US7)."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_api.config import get_settings
from ai_api.db import Base, dispose_engine, get_engine, reset_engine_for_testing
from ai_api.main import create_app


@pytest_asyncio.fixture
async def cors_client(monkeypatch) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173"]')
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
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_preflight_allowed_origin(cors_client: AsyncClient) -> None:
    r = await cors_client.options(
        "/admin/usage",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Admin-Token",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_preflight_disallowed_origin(cors_client: AsyncClient) -> None:
    r = await cors_client.options(
        "/admin/usage",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette CORSMiddleware returns 400 without ACAO when origin not allowed
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.asyncio
async def test_cors_disabled_when_origins_empty(app_client: AsyncClient) -> None:
    """Default cors_origins=[] means CORSMiddleware not registered."""
    r = await app_client.options(
        "/admin/usage",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in r.headers
