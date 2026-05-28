"""Phase 020 US1: /me/allocations carries the model display_name (additive).

Docker-free contract test (in-memory SQLite app_client).
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _seed_model(slug: str, display_name: str) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name=display_name, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=[], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()


async def _member_with_alloc(client: AsyncClient, admin_headers: dict[str, str], email: str, model: str) -> None:
    await client.post(
        "/admin/members", headers=admin_headers,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": email, "resource_model": model},
    )
    assert r.status_code == 201, r.text
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})


# T002 — display_name from catalog
@pytest.mark.asyncio
async def test_me_allocations_has_display_name(app_client: AsyncClient, admin_headers) -> None:
    await _seed_model("azure/m1", "Model One")
    await _member_with_alloc(app_client, admin_headers, "u1@x.com", "azure/m1")
    allocs = (await app_client.get("/me/allocations")).json()
    row = next(a for a in allocs if a["resource_model"] == "azure/m1")
    assert row["display_name"] == "Model One"
    assert "price" in row  # existing field unchanged


# T003 — orphan slug → display_name null
@pytest.mark.asyncio
async def test_me_allocations_orphan_display_name_null(app_client: AsyncClient, admin_headers) -> None:
    await _member_with_alloc(app_client, admin_headers, "u2@x.com", "azure/not-in-catalog")
    allocs = (await app_client.get("/me/allocations")).json()
    row = next(a for a in allocs if a["resource_model"] == "azure/not-in-catalog")
    assert row["display_name"] is None
