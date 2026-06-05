"""Phase 20 US1/US4 — member-level scoped application keys (/me/credentials).

Create a named key over a SET of the member's allocations (one token, many
models); list without plaintext; reject duplicate models / others' allocations;
adjust scope; revoke; rotate.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER


def _stub(model: str) -> dict:
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


def _csrf(c: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: c.cookies.get("aiapi_csrf") or ""}


async def _login(c: AsyncClient, admin: dict[str, str], email: str) -> str:
    await c.post(
        "/admin/members",
        headers=admin,
        json={"email": email, "provider": "local_password", "initial_password": "VerySafePass123", "send_invitation": False},
    )
    await c.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    return (await c.get("/me")).json()["id"]


async def _alloc(c: AsyncClient, admin: dict[str, str], member_id: str, model: str) -> str:
    return (
        await c.post("/admin/allocations", headers=admin, json={"member_id": member_id, "resource_model": model})
    ).json()["id"]


async def _call(c: AsyncClient, token: str, model: str) -> int:
    with patch("ai_api.proxy.upstream.acompletion") as m:
        m.return_value = _stub(model)
        r = await c.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
        )
    return r.status_code


@pytest.mark.asyncio
async def test_create_key_over_two_models_and_list(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "alice@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o")

    r = await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "my-app", "allocation_ids": [a, b]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"].startswith("aiapi_")
    assert {al["resource_model"] for al in body["allocations"]} == {"gpt-4o-mini", "gpt-4o"}

    assert await _call(app_client, body["token"], "gpt-4o-mini") == 200
    assert await _call(app_client, body["token"], "gpt-4o") == 200

    lst = (await app_client.get("/me/credentials")).json()
    assert any(k["name"] == "my-app" for k in lst)
    for k in lst:
        assert "token" not in k
        assert set(k) >= {"id", "name", "token_prefix", "status", "allocations"}


@pytest.mark.asyncio
async def test_create_key_rejects_duplicate_model_and_others_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Bob owns an allocation.
    bob = await _login(app_client, admin_headers, "bob@x.com")
    bob_alloc = await _alloc(app_client, admin_headers, bob, "gpt-4o-mini")
    # Alice has two allocations on the SAME model (duplicate) + her own.
    alice = await _login(app_client, admin_headers, "alice@x.com")
    a1 = await _alloc(app_client, admin_headers, alice, "gpt-4o")
    a2 = await _alloc(app_client, admin_headers, alice, "gpt-4o")  # same model → dup

    dup = await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "dup", "allocation_ids": [a1, a2]})
    assert dup.status_code == 409

    intruder = await app_client.post(
        "/me/credentials", headers=_csrf(app_client), json={"name": "x", "allocation_ids": [a1, bob_alloc]}
    )
    assert intruder.status_code == 403


@pytest.mark.asyncio
async def test_patch_scope_revoke_rotate(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _login(app_client, admin_headers, "carol@x.com")
    a = await _alloc(app_client, admin_headers, mid, "gpt-4o-mini")
    b = await _alloc(app_client, admin_headers, mid, "gpt-4o")
    created = (
        await app_client.post("/me/credentials", headers=_csrf(app_client), json={"name": "k", "allocation_ids": [a]})
    ).json()
    cid, token = created["id"], created["token"]
    assert await _call(app_client, token, "gpt-4o") == 403  # B not in scope yet

    # Add B → same token can now call B.
    pr = await app_client.patch(f"/me/credentials/{cid}", headers=_csrf(app_client), json={"add": [b]})
    assert pr.status_code == 200
    assert await _call(app_client, token, "gpt-4o") == 200

    # Remove A → can't call A; removing all → 409.
    await app_client.patch(f"/me/credentials/{cid}", headers=_csrf(app_client), json={"remove": [a]})
    assert await _call(app_client, token, "gpt-4o-mini") == 403
    empty = await app_client.patch(f"/me/credentials/{cid}", headers=_csrf(app_client), json={"remove": [b]})
    assert empty.status_code == 409

    # Rotate → new token works, old invalid, scope unchanged.
    rot = (await app_client.post(f"/me/credentials/{cid}/rotate", headers=_csrf(app_client))).json()
    assert rot["token"] != token
    assert await _call(app_client, rot["token"], "gpt-4o") == 200
    assert await _call(app_client, token, "gpt-4o") == 401

    # Revoke → all models dead.
    d = await app_client.request("DELETE", f"/me/credentials/{cid}", headers=_csrf(app_client))
    assert d.status_code == 204
    assert await _call(app_client, rot["token"], "gpt-4o") == 401
