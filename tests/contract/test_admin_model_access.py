"""Phase 5 T036 / US3: PATCH /admin/catalog/models/{slug}/access."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _seed_model(slug: str = "test-model") -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug=slug,
                provider="azure",
                display_name="Test",
                family="x",
                description="",
                modality_input=["text"],
                modality_output=["text"],
                capabilities=[],
                context_window=1024,
                cost_tier="low",
                recommended_for=[],
                tags=[],
                example_request={},
                official_doc_url=None,
                status="active",
                deprecation_note=None,
                created_at=now,
                updated_at=now,
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_patch_full_policy(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_model()
    r = await app_client.patch(
        "/admin/catalog/models/test-model/access",
        headers=admin_headers,
        json={
            "default_access": "restricted",
            "allowed_tags": ["eng"],
            "denied_tags": ["contractor"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == "test-model"
    assert body["default_access"] == "restricted"
    assert body["allowed_tags"] == ["eng"]
    assert body["denied_tags"] == ["contractor"]


@pytest.mark.asyncio
async def test_patch_partial_policy(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_model("partial-model")
    r = await app_client.patch(
        "/admin/catalog/models/partial-model/access",
        headers=admin_headers,
        json={"allowed_tags": ["eng"]},
    )
    assert r.status_code == 200
    assert r.json()["default_access"] == "open"  # unchanged


@pytest.mark.asyncio
async def test_patch_unknown_model_returns_404(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.patch(
        "/admin/catalog/models/nope/access",
        headers=admin_headers,
        json={"default_access": "open"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_invalid_tag_format_returns_422(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_model("invalid-tag-model")
    r = await app_client.patch(
        "/admin/catalog/models/invalid-tag-model/access",
        headers=admin_headers,
        json={"allowed_tags": ["BAD"]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "invalid_tag"
