"""Phase 5.1 T005: contract tests for /admin/diagnose/* + /admin/members/{id}/visible-models."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import DefaultAccess, ModelCatalog


async def _seed_model(slug: str, provider: str, default_access: DefaultAccess, allowed: list[str], denied: list[str]) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug,
            provider=provider,
            display_name=slug,
            family="x",
            description="",
            modality_input=["text"],
            modality_output=["text"],
            capabilities=["chat"],
            context_window=1024,
            cost_tier="low",
            recommended_for=[],
            tags=[],
            example_request={},
            official_doc_url=None,
            status="active",
            deprecation_note=None,
            default_access=default_access,
            allowed_tags=allowed,
            denied_tags=denied,
            created_at=now,
            updated_at=now,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_diagnose_unauthenticated_returns_401_or_403(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/diagnose/visibility?member_id=x&model_slug=y")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_diagnose_unknown_member_returns_404(
    app_client: AsyncClient, admin_headers: dict
) -> None:
    await _seed_model("foo/bar", "azure", DefaultAccess.open, [], [])
    r = await app_client.get(
        "/admin/diagnose/visibility?member_id=ghost&model_slug=foo/bar",
        headers=admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_diagnose_unknown_model_returns_404(
    app_client: AsyncClient, admin_headers: dict, member_id: str
) -> None:
    r = await app_client.get(
        f"/admin/diagnose/visibility?member_id={member_id}&model_slug=foo/missing",
        headers=admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_diagnose_credential_gate_fails_when_no_provider_cred(
    app_client: AsyncClient, admin_headers: dict, member_id: str
) -> None:
    await _seed_model("anthropic/x", "anthropic", DefaultAccess.open, [], [])
    r = await app_client.get(
        f"/admin/diagnose/visibility?member_id={member_id}&model_slug=anthropic/x",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["visible"] is False
    assert body["reason_chain"][0]["check"] == "credential_gate"
    assert body["reason_chain"][0]["pass"] is False


@pytest.mark.asyncio
async def test_diagnose_open_model_passes(
    app_client: AsyncClient, admin_headers: dict, member_id: str, make_provider_credential
) -> None:
    await make_provider_credential(provider="azure")
    await _seed_model("azure/o", "azure", DefaultAccess.open, [], [])
    r = await app_client.get(
        f"/admin/diagnose/visibility?member_id={member_id}&model_slug=azure/o",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["visible"] is True


@pytest.mark.asyncio
async def test_visible_models_endpoint(
    app_client: AsyncClient, admin_headers: dict, member_id: str, make_provider_credential
) -> None:
    await make_provider_credential(provider="azure")
    await _seed_model("azure/visible", "azure", DefaultAccess.open, [], [])
    await _seed_model("azure/hidden", "azure", DefaultAccess.restricted, ["vip"], [])
    r = await app_client.get(
        f"/admin/members/{member_id}/visible-models",
        headers=admin_headers,
    )
    assert r.status_code == 200
    slugs = [m["slug"] for m in r.json()]
    assert "azure/visible" in slugs
    assert "azure/hidden" not in slugs


@pytest.mark.asyncio
async def test_visible_models_unknown_member_404(
    app_client: AsyncClient, admin_headers: dict
) -> None:
    r = await app_client.get(
        "/admin/members/ghost/visible-models",
        headers=admin_headers,
    )
    assert r.status_code == 404
