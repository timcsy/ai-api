"""Contract tests for /auth/oidc/start and /auth/oidc/callback (mocked Google)."""
from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient

from ai_api.config import get_settings


def _generate_key_pair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private, pem


_PRIVATE, _PRIVATE_PEM = _generate_key_pair()
_JWK = JsonWebKey.import_key(_PRIVATE_PEM, {"kty": "RSA"})


def _build_id_token(*, sub: str, email: str, name: str, nonce: str, aud: str) -> str:
    header = {"alg": "RS256", "kid": "testkid"}
    now = int(time.time())
    payload = {
        "iss": "https://accounts.google.com",
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": name,
        "nonce": nonce,
        "iat": now,
        "exp": now + 300,
    }
    return jwt.encode(header, payload, _JWK).decode()


def _public_jwk() -> dict:
    pub = _JWK.as_dict(is_private=False)
    pub["kid"] = "testkid"
    pub["alg"] = "RS256"
    pub["use"] = "sig"
    return {"keys": [pub]}


def _discovery() -> dict:
    return {
        "issuer": "https://accounts.google.com",
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
    }


@pytest.fixture(autouse=True)
def _configure_oauth(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("BASE_URL", "http://test")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_oidc_start_302_when_source_allowed(app_client: AsyncClient) -> None:
    with respx.mock(base_url="https://accounts.google.com") as r:
        r.get("/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json=_discovery())
        )
        resp = await app_client.get("/auth/oidc/start?next=/me", follow_redirects=False)
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["location"]
    qs = parse_qs(urlparse(resp.headers["location"]).query)
    assert qs["client_id"] == ["test-client-id"]
    assert qs["state"]


@pytest.mark.asyncio
async def test_oidc_start_blocked_by_source_restriction(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Add a restriction that does NOT cover loopback / 127.0.0.1
    await app_client.post(
        "/admin/source-restrictions",
        headers=admin_headers,
        json={"cidr": "10.0.0.0/8"},
    )
    resp = await app_client.get("/auth/oidc/start")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "source_not_allowed"


@pytest.mark.asyncio
async def test_oidc_callback_full_flow(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Whitelist the test email
    await app_client.post(
        "/admin/whitelist",
        headers=admin_headers,
        json={"email": "user@example.com"},
    )
    # Mock discovery + token + jwks
    with respx.mock() as r:
        r.get("https://accounts.google.com/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json=_discovery())
        )
        r.get("https://www.googleapis.com/oauth2/v3/certs").mock(
            return_value=httpx.Response(200, json=_public_jwk())
        )

        # Start flow to get state + code_verifier on disk
        start = await app_client.get("/auth/oidc/start?next=/me", follow_redirects=False)
        qs = parse_qs(urlparse(start.headers["location"]).query)
        state = qs["state"][0]
        nonce_for_token = None
        # Read OidcState from DB to get nonce (we need it to forge id_token)
        from ai_api.db import get_sessionmaker
        from ai_api.models import OidcState

        sm = get_sessionmaker()
        async with sm() as s:
            nonce_for_token = (await s.get(OidcState, state)).nonce

        id_token = _build_id_token(
            sub="google-sub-1",
            email="user@example.com",
            name="User One",
            nonce=nonce_for_token,
            aud="test-client-id",
        )
        r.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200, json={"id_token": id_token, "access_token": "atok"}
            )
        )

        resp = await app_client.get(
            f"/auth/oidc/callback?code=authcode&state={state}", follow_redirects=False
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/me"
    assert "aiapi_session" in resp.cookies

    # Verify Member was created with provider=google_oidc
    me = await app_client.get("/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "user@example.com"
    assert body["provider"] == "google_oidc"


@pytest.mark.asyncio
async def test_oidc_callback_email_not_allowed(
    app_client: AsyncClient,
) -> None:
    with respx.mock() as r:
        r.get("https://accounts.google.com/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json=_discovery())
        )
        r.get("https://www.googleapis.com/oauth2/v3/certs").mock(
            return_value=httpx.Response(200, json=_public_jwk())
        )

        start = await app_client.get("/auth/oidc/start", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        from ai_api.db import get_sessionmaker
        from ai_api.models import OidcState

        sm = get_sessionmaker()
        async with sm() as s:
            nonce = (await s.get(OidcState, state)).nonce

        id_token = _build_id_token(
            sub="g2",
            email="stranger@nowhere.com",
            name="Stranger",
            nonce=nonce,
            aud="test-client-id",
        )
        r.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )

        resp = await app_client.get(
            f"/auth/oidc/callback?code=authcode&state={state}", follow_redirects=False
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "not_allowed"
