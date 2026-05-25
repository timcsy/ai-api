"""Contract tests for Phase 4 catalog endpoints (US1-US3 + US5)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _make_local_and_login(
    client: AsyncClient, admin_headers: dict[str, str], email: str = "u@x.com"
) -> AsyncClient:
    await client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": email,
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    r = await client.post(
        "/auth/local/login", json={"email": email, "password": "VerySafePass123"}
    )
    assert r.status_code == 200
    return client


async def _seed_models() -> None:
    """Insert 4 models covering the scenarios we need to test filtering.

    Phase 5: also inject an active 'azure' ProviderCredential so the catalog
    credential gate doesn't hide the models from members.
    """
    from ai_api.services.provider_credentials import ProviderCredentialService

    sm = get_sessionmaker()
    now = datetime(2026, 5, 23, tzinfo=UTC)
    async with sm() as s:
        await ProviderCredentialService(s).create(
            provider="azure", label="catalog-test", api_key="azure-test-key-12345"
        )
        await s.commit()
    async with sm() as s:
        s.add_all(
            [
                ModelCatalog(
                    slug="azure/gpt-4o",
                    provider="azure",
                    display_name="GPT-4o",
                    family="gpt-4",
                    description="flagship",
                    modality_input=["text", "image"],
                    modality_output=["text"],
                    capabilities=["chat", "vision", "function-calling"],
                    context_window=128000,
                    cost_tier="high",
                    recommended_for=["chat", "agent"],
                    tags=["multimodal"],
                    example_request={"curl": "...", "body": {}},
                    official_doc_url=None,
                    status="active",
                    deprecation_note=None,
                    created_at=now,
                    updated_at=now,
                ),
                ModelCatalog(
                    slug="azure/gpt-4o-mini",
                    provider="azure",
                    display_name="GPT-4o mini",
                    family="gpt-4",
                    description="cheap multimodal",
                    modality_input=["text", "image"],
                    modality_output=["text"],
                    capabilities=["chat", "vision", "function-calling"],
                    context_window=128000,
                    cost_tier="low",
                    recommended_for=["chat", "agent"],
                    tags=["multimodal", "cost-effective"],
                    example_request={"curl": "...", "body": {}},
                    official_doc_url=None,
                    status="active",
                    deprecation_note=None,
                    created_at=now,
                    updated_at=now,
                ),
                ModelCatalog(
                    slug="azure/dall-e-3",
                    provider="azure",
                    display_name="DALL-E 3",
                    family="dall-e",
                    description="image gen",
                    modality_input=["text"],
                    modality_output=["image"],
                    capabilities=[],
                    context_window=4000,
                    cost_tier="high",
                    recommended_for=["image-gen"],
                    tags=["image-generation"],
                    example_request={"curl": "...", "body": {}},
                    official_doc_url=None,
                    status="active",
                    deprecation_note=None,
                    created_at=now,
                    updated_at=now,
                ),
                ModelCatalog(
                    slug="azure/whisper-old",
                    provider="azure",
                    display_name="Old Whisper",
                    family="whisper",
                    description="deprecated",
                    modality_input=["audio"],
                    modality_output=["text"],
                    capabilities=[],
                    context_window=0,
                    cost_tier="low",
                    recommended_for=["stt"],
                    tags=["speech"],
                    example_request={"curl": "...", "body": {}},
                    official_doc_url=None,
                    status="deprecated",
                    deprecation_note="退役於 2026-04，請改用 azure/whisper-1",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await s.commit()


# ---------------------------------------------------------------------------
# Auth boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_requires_login(app_client: AsyncClient) -> None:
    r = await app_client.get("/catalog/models")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# US1: list + detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(app_client: AsyncClient, admin_headers) -> None:
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/models")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_default_excludes_deprecated(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/models")
    assert r.status_code == 200
    slugs = {m["slug"] for m in r.json()}
    assert "azure/whisper-old" not in slugs  # deprecated hidden
    assert len(r.json()) == 3


@pytest.mark.asyncio
async def test_list_include_deprecated(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/models?include_deprecated=true")
    slugs = {m["slug"] for m in r.json()}
    assert "azure/whisper-old" in slugs
    assert len(r.json()) == 4


@pytest.mark.asyncio
async def test_detail_includes_example_and_deprecation_note(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/models/azure/whisper-old")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deprecated"
    assert body["deprecation_note"]
    assert "example_request" in body


@pytest.mark.asyncio
async def test_detail_404(app_client: AsyncClient, admin_headers) -> None:
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/models/azure/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# US2: multi-AND filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_vision_fn_low_matches_one(
    app_client: AsyncClient, admin_headers
) -> None:
    """SC-002: vision + function-calling + low → only gpt-4o-mini."""
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get(
        "/catalog/models",
        params=[
            ("capability", "vision"),
            ("capability", "function-calling"),
            ("cost_tier", "low"),
        ],
    )
    assert r.status_code == 200
    slugs = [m["slug"] for m in r.json()]
    assert slugs == ["azure/gpt-4o-mini"]


@pytest.mark.asyncio
async def test_filter_modality_output_image(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get(
        "/catalog/models", params=[("modality_output", "image")]
    )
    slugs = [m["slug"] for m in r.json()]
    assert slugs == ["azure/dall-e-3"]


@pytest.mark.asyncio
async def test_filter_no_match_returns_empty_200(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get(
        "/catalog/models", params=[("cost_tier", "ultra")]
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_filter_min_context_window(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get(
        "/catalog/models?min_context_window=100000"
    )
    slugs = sorted([m["slug"] for m in r.json()])
    assert slugs == ["azure/gpt-4o", "azure/gpt-4o-mini"]


# ---------------------------------------------------------------------------
# US3: facet API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_facets_empty_db_returns_stable_schema(
    app_client: AsyncClient, admin_headers
) -> None:
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/filters")
    body = r.json()
    assert set(body.keys()) == {
        "modality_input",
        "modality_output",
        "capabilities",
        "cost_tier",
        "recommended_for",
        "family",
        "tags",
    }
    for v in body.values():
        assert v == {}


@pytest.mark.asyncio
async def test_facets_counts_and_excludes_deprecated(
    app_client: AsyncClient, admin_headers
) -> None:
    await _seed_models()
    await _make_local_and_login(app_client, admin_headers)
    r = await app_client.get("/catalog/filters")
    body = r.json()
    # 3 active models; whisper-old (deprecated) NOT counted
    assert body["cost_tier"] == {"high": 2, "low": 1}
    assert body["modality_input"] == {"text": 3, "image": 2}
    assert "audio" not in body["modality_input"]  # only on deprecated
