"""OAuth 2.0 Authorization Code + PKCE flow (first-party web apps).

Full flow: consent → approve → token exchange → key. Plus the security checks
that matter: redirect_uri allowlist, PKCE verification, single-use code,
redirect_uri binding, deny path, and auth requirement.
"""
from __future__ import annotations

import base64
import hashlib
import secrets

import pytest
from httpx import AsyncClient

from ai_api.api.deps import CSRF_HEADER

REDIRECT = "https://app.test/callback"


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


async def _login_with_allocation(client: AsyncClient, admin_headers: dict[str, str], email: str) -> str:
    await client.post(
        "/admin/members", headers=admin_headers,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    me = (await client.get("/me")).json()
    alloc = (await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
    )).json()
    return alloc["id"]


async def _consent(client: AsyncClient, challenge: str, redirect: str = REDIRECT) -> dict:
    return (await client.post(
        "/me/oauth/consent", headers=_csrf(client),
        json={"client_name": "My Transcriber", "redirect_uri": redirect,
              "code_challenge": challenge, "code_challenge_method": "S256", "state": "xyz123"},
    ))


@pytest.mark.asyncio
async def test_full_flow_consent_approve_exchange(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _login_with_allocation(app_client, admin_headers, "oauth-a@x.com")
    verifier, challenge = _pkce()

    c = await _consent(app_client, challenge)
    assert c.status_code == 200, c.text
    cid = c.json()["id"]
    assert any(a["id"] == alloc for a in c.json()["allocations"])

    appr = await app_client.post(
        f"/me/oauth/{cid}/approve", headers=_csrf(app_client),
        json={"allocation_ids": [alloc]},
    )
    assert appr.status_code == 200, appr.text
    body = appr.json()
    assert body["redirect_uri"] == REDIRECT and body["state"] == "xyz123"
    code = body["code"]

    tok = await app_client.post(
        "/oauth/token",
        json={"grant_type": "authorization_code", "code": code,
              "redirect_uri": REDIRECT, "code_verifier": verifier},
    )
    assert tok.status_code == 200, tok.text
    assert tok.json()["access_token"].startswith("aiapi_")
    assert tok.json()["credential_id"]

    # single-use: exchanging the same code again fails
    again = await app_client.post(
        "/oauth/token",
        json={"grant_type": "authorization_code", "code": code,
              "redirect_uri": REDIRECT, "code_verifier": verifier},
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_grant"


@pytest.mark.asyncio
async def test_redirect_uri_not_on_allowlist_rejected(app_client: AsyncClient, admin_headers) -> None:
    await _login_with_allocation(app_client, admin_headers, "oauth-b@x.com")
    _, challenge = _pkce()
    c = await _consent(app_client, challenge, redirect="https://evil.example/steal")
    assert c.status_code == 400
    assert c.json()["detail"]["error"]["code"] == "redirect_uri_not_allowed"


@pytest.mark.asyncio
async def test_pkce_mismatch_rejected(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _login_with_allocation(app_client, admin_headers, "oauth-c@x.com")
    _, challenge = _pkce()
    cid = (await _consent(app_client, challenge)).json()["id"]
    code = (await app_client.post(
        f"/me/oauth/{cid}/approve", headers=_csrf(app_client), json={"allocation_ids": [alloc]},
    )).json()["code"]
    tok = await app_client.post(
        "/oauth/token",
        json={"grant_type": "authorization_code", "code": code,
              "redirect_uri": REDIRECT, "code_verifier": "wrong-verifier-entirely"},
    )
    assert tok.status_code == 400 and tok.json()["error"]["code"] == "invalid_grant"


@pytest.mark.asyncio
async def test_redirect_uri_mismatch_at_token_rejected(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _login_with_allocation(app_client, admin_headers, "oauth-d@x.com")
    verifier, challenge = _pkce()
    cid = (await _consent(app_client, challenge)).json()["id"]
    code = (await app_client.post(
        f"/me/oauth/{cid}/approve", headers=_csrf(app_client), json={"allocation_ids": [alloc]},
    )).json()["code"]
    tok = await app_client.post(
        "/oauth/token",
        json={"grant_type": "authorization_code", "code": code,
              "redirect_uri": "https://myapp.example/other", "code_verifier": verifier},
    )
    assert tok.status_code == 400 and tok.json()["error"]["code"] == "invalid_grant"


@pytest.mark.asyncio
async def test_deny_returns_access_denied(app_client: AsyncClient, admin_headers) -> None:
    await _login_with_allocation(app_client, admin_headers, "oauth-e@x.com")
    _, challenge = _pkce()
    cid = (await _consent(app_client, challenge)).json()["id"]
    d = await app_client.post(f"/me/oauth/{cid}/deny", headers=_csrf(app_client))
    assert d.status_code == 200
    assert d.json()["error"] == "access_denied" and d.json()["state"] == "xyz123"


@pytest.mark.asyncio
async def test_consent_requires_session(app_client: AsyncClient) -> None:
    _, challenge = _pkce()
    r = await app_client.post(
        "/me/oauth/consent", headers=_csrf(app_client),
        json={"client_name": "X", "redirect_uri": REDIRECT,
              "code_challenge": challenge, "code_challenge_method": "S256"},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_can_edit_redirect_allowlist(app_client: AsyncClient, admin_headers) -> None:
    """The allowlist is an admin-editable DB singleton (lazy-seeded from env). A
    PUT takes effect immediately and overrides the env default."""
    # lazy-seed reflects the env default
    got = await app_client.get("/admin/oauth/config", headers=admin_headers)
    assert got.status_code == 200
    assert "https://app.test/" in got.json()["prefixes"]

    # narrow the allowlist to a different origin
    put = await app_client.put(
        "/admin/oauth/config", headers=admin_headers,
        json={"redirect_allowlist": "https://newapp.test/"},
    )
    assert put.status_code == 200
    assert put.json()["prefixes"] == ["https://newapp.test/"]

    await _login_with_allocation(app_client, admin_headers, "oauth-cfg@x.com")
    _, challenge = _pkce()
    # the previously-allowed origin is now rejected (DB overrides env)
    old = await _consent(app_client, challenge, redirect="https://app.test/callback")
    assert old.status_code == 400 and old.json()["detail"]["error"]["code"] == "redirect_uri_not_allowed"
    # the newly-allowed origin works
    neu = await _consent(app_client, challenge, redirect="https://newapp.test/cb")
    assert neu.status_code == 200


@pytest.mark.asyncio
async def test_admin_oauth_config_requires_admin(app_client: AsyncClient) -> None:
    assert (await app_client.get("/admin/oauth/config")).status_code in (401, 403)
    assert (
        await app_client.put("/admin/oauth/config", json={"redirect_allowlist": "https://x/"})
    ).status_code in (401, 403)


@pytest.mark.asyncio
async def test_unsupported_grant_type(app_client: AsyncClient) -> None:
    r = await app_client.post(
        "/oauth/token",
        json={"grant_type": "password", "code": "x", "redirect_uri": REDIRECT, "code_verifier": "y"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_grant_type"
