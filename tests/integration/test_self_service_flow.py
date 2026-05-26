"""Phase 6 T017 / US3: end-to-end self-service claim → call → revoke → lock → unlock."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER
from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, ModelCatalog


def _stub() -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "test",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _seed(slug: str = "azure/ss-flow") -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug=slug, provider="azure", display_name="SS Flow", family="x",
                description="", modality_input=["text"], modality_output=["text"],
                capabilities=["chat"], context_window=1024, cost_tier="low",
                recommended_for=[], tags=[], example_request={}, official_doc_url=None,
                status="active", deprecation_note=None, created_at=now, updated_at=now,
                default_access="open", allowed_tags=[], denied_tags=[],
                self_service_enabled=True, self_service_default_quota=50000,
            )
        )
        await s.commit()


async def _login(client: AsyncClient, admin_headers: dict[str, str], email: str) -> dict:
    await client.post(
        "/admin/members", headers=admin_headers,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return (await client.get("/me")).json()


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


async def _audit_types(target_id: str) -> set[str]:
    from sqlalchemy import select

    from ai_api.models import AuthAuditLog

    sm = get_sessionmaker()
    async with sm() as s:
        rows = (
            await s.execute(select(AuthAuditLog).where(AuthAuditLog.target_id == target_id))
        ).scalars().all()
    return {r.event_type.value if hasattr(r.event_type, "value") else r.event_type for r in rows}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_self_service_full_lifecycle(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-flow")
    await _seed()
    me = await _login(app_client, admin_headers, "flow@x.com")

    # 1. claim
    r = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/ss-flow"})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    alloc_id = r.json()["allocation"]["id"]

    # 2. the claimed token can call /v1
    with patch("litellm.acompletion", return_value=_stub()):
        rc = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "azure/ss-flow", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert rc.status_code == 200, rc.text

    # 3. admin revokes → locks re-claim
    rv = await app_client.delete(f"/admin/allocations/{alloc_id}", headers=admin_headers)
    assert rv.status_code == 200

    # 4. re-claim blocked
    r2 = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/ss-flow"})
    assert r2.status_code == 403
    assert r2.json()["detail"]["error"]["code"] == "reclaim_locked"

    # 5. lock appears in admin list
    locks = (await app_client.get("/admin/self-service-locks", headers=admin_headers)).json()
    assert any(lk["member_id"] == me["id"] and lk["model_slug"] == "azure/ss-flow" for lk in locks)

    # 6. admin unlock
    ru = await app_client.post(
        "/admin/self-service-locks/unlock", headers=admin_headers,
        json={"member_id": me["id"], "model_slug": "azure/ss-flow"},
    )
    assert ru.status_code == 204

    # 7. claim again succeeds
    r3 = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/ss-flow"})
    assert r3.status_code == 201, r3.text

    # 8. audit trail
    types = await _audit_types(me["id"])
    assert AuditEventType.self_service_reclaim_locked.value in types
    assert AuditEventType.self_service_unlocked.value in types
    model_types = await _audit_types("azure/ss-flow")
    assert AuditEventType.self_service_claimed.value in model_types


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoking_admin_allocation_does_not_lock(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-adm")
    await _seed("azure/ss-adm")
    me = await _login(app_client, admin_headers, "adm@x.com")

    # admin manually creates (origin=admin) an allocation, then revokes it
    created = await app_client.post(
        "/admin/allocations", headers=admin_headers,
        json={"member_id": me["id"], "resource_model": "azure/ss-adm"},
    )
    alloc_id = created.json()["id"]
    await app_client.delete(f"/admin/allocations/{alloc_id}", headers=admin_headers)

    # no lock created → member can still self-claim
    locks = (await app_client.get("/admin/self-service-locks", headers=admin_headers)).json()
    assert not any(lk["model_slug"] == "azure/ss-adm" for lk in locks)
    r = await app_client.post("/me/allocations", headers=_csrf(app_client), json={"model": "azure/ss-adm"})
    assert r.status_code == 201, r.text
