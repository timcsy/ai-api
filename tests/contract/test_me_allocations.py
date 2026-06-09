"""Phase 6 T013 / US2: POST /me/allocations self-service claim.

Contract: specs/015-self-service-allocation/contracts/me-allocations.yaml
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER
from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _seed_model(
    slug: str,
    *,
    provider: str = "azure",
    enabled: bool = True,
    quota: int | None = 50000,
    default_access: str = "open",
    allowed: list[str] | None = None,
) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug=slug, provider=provider, display_name="M", family="x",
                description="", modality_input=["text"], modality_output=["text"],
                capabilities=[], context_window=1024, cost_tier="low",
                recommended_for=[], tags=[], example_request={}, official_doc_url=None,
                status="active", deprecation_note=None, created_at=now, updated_at=now,
                default_access=default_access, allowed_tags=allowed or [], denied_tags=[],
                self_service_enabled=enabled, self_service_default_quota=quota,
            )
        )
        await s.commit()


async def _login(client: AsyncClient, admin_headers: dict[str, str], email: str = "claimer@x.com") -> dict:
    await client.post(
        "/admin/members",
        headers=admin_headers,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return (await client.get("/me")).json()


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


@pytest.mark.asyncio
async def test_claim_success(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-1")
    await _seed_model("azure/open-ss")
    await _login(app_client, admin_headers)
    r = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/open-ss"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"].startswith("aiapi_")
    assert body["allocation"]["origin"] == "self_service"
    assert body["allocation"]["quota_tokens_per_month"] == 50000
    assert body["allocation"]["status"] == "active"


# Phase 11 — member self-service pause / resume of own allocation
@pytest.mark.asyncio
async def test_member_pause_and_resume_own_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-pr")
    await _seed_model("azure/pr-model")
    await _login(app_client, admin_headers)
    claim = await app_client.post(
        "/me/allocations", headers=_csrf(app_client), json={"model": "azure/pr-model"}
    )
    alloc_id = claim.json()["allocation"]["id"]

    # pause → paused
    r = await app_client.post(f"/me/allocations/{alloc_id}/pause", headers=_csrf(app_client))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"
    # resume → active
    r = await app_client.post(f"/me/allocations/{alloc_id}/resume", headers=_csrf(app_client))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_member_cannot_pause_others_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-pr2")
    await _seed_model("azure/pr-model2")
    # member A claims
    await _login(app_client, admin_headers, email="owner@x.com")
    claim = await app_client.post(
        "/me/allocations", headers=_csrf(app_client), json={"model": "azure/pr-model2"}
    )
    alloc_id = claim.json()["allocation"]["id"]
    # member B logs in, tries to pause A's allocation
    await _login(app_client, admin_headers, email="intruder@x.com")
    r = await app_client.post(f"/me/allocations/{alloc_id}/pause", headers=_csrf(app_client))
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_claim_model_not_self_service(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-2")
    await _seed_model("azure/closed", enabled=False, quota=None)
    await _login(app_client, admin_headers)
    r = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/closed"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "model_not_self_service"


@pytest.mark.asyncio
async def test_claim_model_forbidden(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-3")
    await _seed_model("azure/restricted", default_access="restricted", allowed=["eng"])
    await _login(app_client, admin_headers)  # member has no 'eng' tag
    r = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/restricted"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "model_forbidden"


@pytest.mark.asyncio
async def test_claim_already_claimed(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-4")
    await _seed_model("azure/dup")
    await _login(app_client, admin_headers)
    r1 = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/dup"})
    assert r1.status_code == 201
    r2 = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/dup"})
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"]["code"] == "already_claimed"


@pytest.mark.asyncio
async def test_claim_unknown_model_404(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _login(app_client, admin_headers)
    r = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "nope/x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_claim_requires_session(app_client: AsyncClient) -> None:
    r = await app_client.post("/me/allocations", json={"model": "azure/open-ss"})
    assert r.status_code in (401, 403)


# Phase 27 (037): GET /me/allocations carries derived `agent_compatible`
async def _seed_caps(slug: str, capabilities: list[str]) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name="M", family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=capabilities, context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_me_allocations_agent_compatible(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    me = await _login(app_client, admin_headers, email="ac@x.com")
    mid = me["id"]
    await _seed_caps("azure/agent", ["chat", "responses"])   # available → true
    await _seed_caps("azure/plain", ["chat"])                # unknown → false
    # orphan: azure/ghost has NO catalog row → false
    for model in ("azure/agent", "azure/plain", "azure/ghost"):
        r = await app_client.post(
            "/admin/allocations", headers=admin_headers,
            json={"member_id": mid, "resource_model": model},
        )
        assert r.status_code in (200, 201), r.text

    rows = (await app_client.get("/me/allocations")).json()
    by_model = {a["resource_model"]: a for a in rows}
    assert by_model["azure/agent"]["agent_compatible"] is True
    assert by_model["azure/plain"]["agent_compatible"] is False
    assert by_model["azure/ghost"]["agent_compatible"] is False
