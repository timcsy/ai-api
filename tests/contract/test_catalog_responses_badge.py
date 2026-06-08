"""Phase 25 US4 (FR-005): member catalog exposes a responses "Agent 相容" badge +
source, strips internal responses:* markers, and lets members filter for available."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog
from ai_api.services import responses_support as rs


async def _login(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await client.post(
        "/admin/members", headers=admin_headers,
        json={"email": "u@x.com", "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    r = await client.post("/auth/local/login",
                          json={"email": "u@x.com", "password": "VerySafePass123"})
    assert r.status_code == 200


async def _seed_azure_cred() -> None:
    # credential gate: a provider needs an active credential for its models to show.
    from ai_api.services.provider_credentials import ProviderCredentialService

    sm = get_sessionmaker()
    async with sm() as s:
        await ProviderCredentialService(s).create(
            provider="azure", label="badge-test", api_key="azure-test-key-12345"
        )
        await s.commit()


async def _seed(slug: str, caps: list[str]) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name=slug, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=caps, context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_badge_and_source_and_internal_markers_stripped(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed("azure/avail", ["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    await _seed("azure/unknown", ["chat"])
    await _seed_azure_cred()
    await _login(app_client, admin_headers)

    rows = (await app_client.get("/catalog/models")).json()
    by_slug = {r["slug"]: r for r in rows}

    avail = by_slug["azure/avail"]
    # bare `responses` badge kept; colon markers stripped
    assert "responses" in avail["capabilities"]
    assert all(not c.startswith("responses:") for c in avail["capabilities"])
    assert avail["responses_support"] == {"state": "available", "source": "tested"}

    unknown = by_slug["azure/unknown"]
    assert "responses" not in unknown["capabilities"]
    assert unknown["responses_support"] == {"state": "unknown", "source": None}


@pytest.mark.asyncio
async def test_filter_agent_compatible_lists_only_available(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed("azure/avail", ["chat", rs.RESPONSES, rs.RESPONSES_MANUAL])
    await _seed("azure/blocked", ["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    await _seed("azure/unknown", ["chat"])
    await _seed_azure_cred()
    await _login(app_client, admin_headers)

    rows = (await app_client.get("/catalog/models?capability=responses")).json()
    slugs = {r["slug"] for r in rows}
    assert slugs == {"azure/avail"}


@pytest.mark.asyncio
async def test_filters_facet_hides_internal_markers(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed("azure/avail", ["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    await _seed("azure/blocked", ["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    await _seed_azure_cred()
    await _login(app_client, admin_headers)

    facets = (await app_client.get("/catalog/filters")).json()
    caps = facets["capabilities"]
    assert "responses" in caps
    assert not any(k.startswith("responses:") for k in caps)
