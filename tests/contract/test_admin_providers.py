"""Phase 5 T024 / US2: contract tests for /admin/providers CRUD + rotate + disable.

Spec contract: specs/012-multi-provider-access/contracts/providers.yaml
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

_PAYLOAD = {
    "provider": "anthropic",
    "label": "team-a-prod",
    "api_key": "sk-ant-test-12345678",
}


@pytest.mark.asyncio
async def test_unauthenticated_list_returns_401_or_403(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/providers")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_returns_201_with_plaintext_api_key(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider"] == "anthropic"
    assert body["label"] == "team-a-prod"
    assert body["api_key"] == _PAYLOAD["api_key"]  # one-time plaintext echo
    assert body["status"] == "active"
    assert len(body["fingerprint"]) == 16


@pytest.mark.asyncio
async def test_get_does_not_return_api_key(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    create = await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    cred_id = create.json()["id"]
    r = await app_client.get(f"/admin/providers/{cred_id}", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "api_key" not in body
    assert body["fingerprint"]


@pytest.mark.asyncio
async def test_list_does_not_return_api_key(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    r = await app_client.get("/admin/providers", headers=admin_headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert "api_key" not in rows[0]


@pytest.mark.asyncio
async def test_duplicate_provider_label_returns_409(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    r = await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "duplicate_label"


@pytest.mark.asyncio
async def test_provider_not_in_allowlist_returns_422(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    bad = {**_PAYLOAD, "provider": "bogusprov"}
    r = await app_client.post("/admin/providers", headers=admin_headers, json=bad)
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "provider_not_allowed"


@pytest.mark.asyncio
async def test_rotate_changes_fingerprint_and_returns_new_plaintext(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    create = await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    cred_id = create.json()["id"]
    old_fp = create.json()["fingerprint"]
    r = await app_client.post(
        f"/admin/providers/{cred_id}/rotate",
        headers=admin_headers,
        json={"api_key": "sk-ant-rotated-87654321"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["api_key"] == "sk-ant-rotated-87654321"
    assert body["fingerprint"] != old_fp
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_rotate_disabled_returns_409(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    create = await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    cred_id = create.json()["id"]
    await app_client.post(f"/admin/providers/{cred_id}/disable", headers=admin_headers)
    r = await app_client.post(
        f"/admin/providers/{cred_id}/rotate",
        headers=admin_headers,
        json={"api_key": "another-key-12345"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "cannot_rotate"


@pytest.mark.asyncio
async def test_disable_returns_200_then_409(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    create = await app_client.post("/admin/providers", headers=admin_headers, json=_PAYLOAD)
    cred_id = create.json()["id"]
    r1 = await app_client.post(f"/admin/providers/{cred_id}/disable", headers=admin_headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "disabled"
    assert r1.json()["disabled_at"] is not None
    r2 = await app_client.post(f"/admin/providers/{cred_id}/disable", headers=admin_headers)
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"]["code"] == "already_disabled"


@pytest.mark.asyncio
async def test_not_found_returns_404(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get("/admin/providers/nonexistent", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_short_api_key_returns_422(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    bad = {**_PAYLOAD, "api_key": "short"}
    r = await app_client.post("/admin/providers", headers=admin_headers, json=bad)
    assert r.status_code == 422
