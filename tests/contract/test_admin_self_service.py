"""Phase 6 T008 / US1: PATCH /admin/catalog/models/{slug}/self-service
+ GET /admin/self-service-locks + POST unlock.

Contract: specs/015-self-service-allocation/contracts/admin-self-service.yaml
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _seed_model(slug: str = "azure/ss-model") -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug=slug, provider="azure", display_name="SS", family="x",
                description="", modality_input=["text"], modality_output=["text"],
                capabilities=[], context_window=1024, cost_tier="low",
                recommended_for=[], tags=[], example_request={}, official_doc_url=None,
                status="active", deprecation_note=None, created_at=now, updated_at=now,
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_enable_with_quota(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_model()
    r = await app_client.patch(
        "/admin/catalog/models/azure/ss-model/self-service",
        headers=admin_headers,
        json={"enabled": True, "default_quota": 50000},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["self_service_enabled"] is True
    assert body["self_service_default_quota"] == 50000


@pytest.mark.asyncio
async def test_enable_without_quota_422(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_model("azure/ss-noquota")
    r = await app_client.patch(
        "/admin/catalog/models/azure/ss-noquota/self-service",
        headers=admin_headers,
        json={"enabled": True},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "quota_required"


@pytest.mark.asyncio
async def test_disable(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_model("azure/ss-disable")
    await app_client.patch(
        "/admin/catalog/models/azure/ss-disable/self-service",
        headers=admin_headers, json={"enabled": True, "default_quota": 100},
    )
    r = await app_client.patch(
        "/admin/catalog/models/azure/ss-disable/self-service",
        headers=admin_headers, json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["self_service_enabled"] is False


@pytest.mark.asyncio
async def test_unknown_model_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.patch(
        "/admin/catalog/models/nope/self-service",
        headers=admin_headers, json={"enabled": False},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_requires_admin(app_client: AsyncClient) -> None:
    r = await app_client.patch(
        "/admin/catalog/models/x/self-service", json={"enabled": False}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_locks_list_empty(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/self-service-locks", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []
