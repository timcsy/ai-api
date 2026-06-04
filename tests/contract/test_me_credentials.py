"""Contract tests: per-device credentials under /me (Phase 18, US1 + US2).

Covers: add returns plaintext once + callable; multiple credentials bill the
same allocation; list never leaks plaintext; revoke one is isolated; owner
boundary (member cannot touch another member's credentials).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER


def _stub_litellm_response() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


async def _login_with_allocation(
    client: AsyncClient, admin_headers: dict[str, str], email: str = "alice@x.com"
) -> tuple[str, str]:
    """Create + login a member and give them one allocation. Returns
    (allocation_id, default_token)."""
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
    await client.post(
        "/auth/local/login", json={"email": email, "password": "VerySafePass123"}
    )
    me = (await client.get("/me")).json()
    alloc = (
        await client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    return alloc["id"], alloc["token"]


async def _call_proxy(client: AsyncClient, token: str) -> int:
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub_litellm_response()
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    return r.status_code


@pytest.mark.asyncio
async def test_add_credential_returns_token_once_and_callable(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id, _ = await _login_with_allocation(app_client, admin_headers)

    r = await app_client.post(
        f"/me/allocations/{alloc_id}/credentials",
        headers=_csrf(app_client),
        json={"name": "筆電"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "筆電"
    assert body["token"].startswith("aiapi_")
    assert body["token_prefix"] and body["token_prefix"] in body["token"]
    assert "id" in body

    # The freshly issued token can call the proxy.
    assert await _call_proxy(app_client, body["token"]) == 200


@pytest.mark.asyncio
async def test_multiple_credentials_bill_same_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id, default_token = await _login_with_allocation(app_client, admin_headers)

    r = await app_client.post(
        f"/me/allocations/{alloc_id}/credentials",
        headers=_csrf(app_client),
        json={"name": "桌機"},
    )
    second_token = r.json()["token"]

    assert await _call_proxy(app_client, default_token) == 200
    assert await _call_proxy(app_client, second_token) == 200

    # Both calls are attributed to the same allocation.
    calls = (
        await app_client.get(f"/me/allocations/{alloc_id}/calls")
    ).json()
    assert len(calls["items"]) == 2


@pytest.mark.asyncio
async def test_list_credentials_no_plaintext(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id, _ = await _login_with_allocation(app_client, admin_headers)
    await app_client.post(
        f"/me/allocations/{alloc_id}/credentials",
        headers=_csrf(app_client),
        json={"name": "平板"},
    )

    r = await app_client.get(f"/me/allocations/{alloc_id}/credentials")
    assert r.status_code == 200
    creds = r.json()
    assert len(creds) == 2  # default + 平板
    names = {c["name"] for c in creds}
    assert names == {"預設", "平板"}
    for c in creds:
        assert "token" not in c  # never leak plaintext
        assert set(c) >= {"id", "name", "token_prefix", "created_at", "status"}
        assert c["status"] == "active"


@pytest.mark.asyncio
async def test_revoke_one_does_not_affect_others(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id, default_token = await _login_with_allocation(app_client, admin_headers)
    add = await app_client.post(
        f"/me/allocations/{alloc_id}/credentials",
        headers=_csrf(app_client),
        json={"name": "筆電"},
    )
    cred = add.json()
    second_token = cred["token"]

    # Revoke the second credential only.
    r = await app_client.request(
        "DELETE",
        f"/me/allocations/{alloc_id}/credentials/{cred['id']}",
        headers=_csrf(app_client),
    )
    assert r.status_code == 204

    assert await _call_proxy(app_client, second_token) == 401  # revoked → rejected
    assert await _call_proxy(app_client, default_token) == 200  # untouched


@pytest.mark.asyncio
async def test_revoke_owner_isolation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Bob owns an allocation with a credential.
    bob_alloc, _ = await _login_with_allocation(app_client, admin_headers, email="bob@x.com")
    bob_cred = (
        await app_client.post(
            f"/me/allocations/{bob_alloc}/credentials",
            headers=_csrf(app_client),
            json={"name": "bob-laptop"},
        )
    ).json()
    # Clear bob's session by logging in as alice.
    await _login_with_allocation(app_client, admin_headers, email="alice@x.com")

    # Alice must not GET / POST / DELETE on bob's allocation or credential.
    assert (
        await app_client.get(f"/me/allocations/{bob_alloc}/credentials")
    ).status_code == 403
    assert (
        await app_client.post(
            f"/me/allocations/{bob_alloc}/credentials",
            headers=_csrf(app_client),
            json={"name": "intruder"},
        )
    ).status_code == 403
    assert (
        await app_client.request(
            "DELETE",
            f"/me/allocations/{bob_alloc}/credentials/{bob_cred['id']}",
            headers=_csrf(app_client),
        )
    ).status_code == 403
