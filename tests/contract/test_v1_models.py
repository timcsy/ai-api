"""Phase 36 (spec 050) — OpenAI 相容模型發現端點 GET /v1/models, /v1/models/{id}.

Contract: list/retrieve return the calling KEY's scope (active allocations only),
OpenAI-compatible shape; ids round-trip as `model`; 401 without auth; 404 out of
scope. See specs/050-openai-models-copilot/contracts/v1-models.md.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER


def _csrf(c: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: c.cookies.get("aiapi_csrf") or ""}


async def _login(c: AsyncClient, admin: dict[str, str], email: str) -> str:
    await c.post(
        "/admin/members",
        headers=admin,
        json={
            "email": email,
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    await c.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return (await c.get("/me")).json()["id"]


async def _alloc(c: AsyncClient, admin: dict[str, str], member_id: str, model: str) -> str:
    return (
        await c.post(
            "/admin/allocations",
            headers=admin,
            json={"member_id": member_id, "resource_model": model},
        )
    ).json()["id"]


async def _key(c: AsyncClient, allocation_ids: list[str], name: str = "k") -> dict:
    r = await c.post(
        "/me/credentials",
        headers=_csrf(c),
        json={"name": name, "allocation_ids": allocation_ids},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _chat_stub(model: str) -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.asyncio
async def test_list_models_scope_match(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """SC-001: list == the key's active-allocation models, OpenAI list shape."""
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    b = await _alloc(app_client, admin_headers, mid, "text-embedding-3-large")
    key = await _key(app_client, [a, b], name="my-app")

    r = await app_client.get("/v1/models", headers={"Authorization": f"Bearer {key['token']}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["object"] == "list"
    assert {m["id"] for m in body["data"]} == {"gpt-4o-mini", "text-embedding-3-large"}
    for m in body["data"]:
        assert m["object"] == "model"
        assert "created" in m and "owned_by" in m
    # unpriced models (no price seeded here) are still listed (FR-007)


@pytest.mark.asyncio
async def test_list_models_401_no_token(app_client: AsyncClient) -> None:
    r = await app_client.get("/v1/models")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert "data" not in r.json()  # no model info leaked


@pytest.mark.asyncio
async def test_list_models_scope_isolation(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """Two keys with different scopes see only their own models."""
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    k1 = await _key(app_client, [a], name="k1")
    k2 = await _key(app_client, [b], name="k2")

    r1 = await app_client.get("/v1/models", headers={"Authorization": f"Bearer {k1['token']}"})
    r2 = await app_client.get("/v1/models", headers={"Authorization": f"Bearer {k2['token']}"})
    assert {m["id"] for m in r1.json()["data"]} == {"gpt-4o"}
    assert {m["id"] for m in r2.json()["data"]} == {"gpt-4o-mini"}


@pytest.mark.asyncio
async def test_retrieve_model_symmetry(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    key = await _key(app_client, [a])
    auth = {"Authorization": f"Bearer {key['token']}"}

    ok = await app_client.get("/v1/models/gpt-4o", headers=auth)
    assert ok.status_code == 200, ok.text
    assert ok.json()["id"] == "gpt-4o"
    assert ok.json()["object"] == "model"

    miss = await app_client.get("/v1/models/does-not-exist", headers=auth)
    assert miss.status_code == 404
    assert miss.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_retrieve_401_no_token(app_client: AsyncClient) -> None:
    r = await app_client.get("/v1/models/gpt-4o")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_list_excludes_revoked_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """FR-006: a revoked (non-active) allocation's model drops from the list."""
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    key = await _key(app_client, [a, b])
    auth = {"Authorization": f"Bearer {key['token']}"}

    rv = await app_client.delete(f"/admin/allocations/{a}", headers=admin_headers)
    assert rv.status_code in (200, 204), rv.text

    r = await app_client.get("/v1/models", headers=auth)
    assert {m["id"] for m in r.json()["data"]} == {"gpt-4o-mini"}
    # retrieve the revoked one → 404 (no longer in active scope)
    miss = await app_client.get("/v1/models/gpt-4o", headers=auth)
    assert miss.status_code == 404


@pytest.mark.asyncio
async def test_list_id_is_callable(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """SC-002: any id from the list, used as `model`, routes (no model_mismatch)."""
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    key = await _key(app_client, [a])
    auth = {"Authorization": f"Bearer {key['token']}"}

    listed = (await app_client.get("/v1/models", headers=auth)).json()["data"]
    model_id = listed[0]["id"]
    with patch("ai_api.proxy.upstream.acompletion") as m:
        m.return_value = _chat_stub(model_id)
        call = await app_client.post(
            "/v1/chat/completions",
            headers=auth,
            json={"model": model_id, "messages": [{"role": "user", "content": "hi"}]},
        )
    assert call.status_code == 200, call.text
