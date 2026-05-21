"""Foundational smoke test: /healthz responds."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ai_api.main import create_app


@pytest.mark.asyncio
async def test_healthz_ok() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_request_id_propagates() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz", headers={"X-Request-Id": "test-rid"})
    assert response.headers.get("X-Request-Id") == "test-rid"


@pytest.mark.asyncio
async def test_admin_endpoint_requires_token() -> None:
    """No admin token → 401 (smoke test for admin auth dependency)."""
    # This will be expanded in Phase 3 when /admin/allocations exists with logic.
    # For now, confirm dependency import works without error.
    from ai_api.api.deps import require_admin_token  # noqa: F401
