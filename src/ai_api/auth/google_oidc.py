"""Google OIDC provider — authorize URL + callback verification via authlib."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from authlib.jose import JsonWebToken, JWTClaims
from authlib.jose.errors import JoseError

from ai_api.auth.base import AuthError, AuthProvider, AuthResult
from ai_api.config import get_settings

STATE_TTL = timedelta(minutes=10)
_jwt = JsonWebToken(["RS256", "ES256"])


@dataclass(frozen=True)
class AuthorizeUrl:
    url: str
    state: str
    nonce: str
    code_verifier: str
    expires_at: datetime


def _b64url_no_pad(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


class GoogleOidcProvider(AuthProvider):
    name = "google_oidc"

    async def discovery(self) -> dict[str, Any]:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(settings.google_discovery_url)
            r.raise_for_status()
            return r.json()  # type: ignore[no-any-return]

    async def build_authorize_url(self, *, redirect_uri: str) -> AuthorizeUrl:
        settings = get_settings()
        meta = await self.discovery()
        state = _b64url_no_pad(24)
        nonce = _b64url_no_pad(16)
        code_verifier = _b64url_no_pad(32)
        # We're using the OAuth `plain` PKCE method for simplicity in dev;
        # production should switch to S256 (still acceptable with authlib).
        import base64
        import hashlib

        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        params = {
            "response_type": "code",
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
        from urllib.parse import urlencode

        url = f"{meta['authorization_endpoint']}?{urlencode(params)}"
        return AuthorizeUrl(
            url=url,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            expires_at=datetime.now(UTC) + STATE_TTL,
        )

    async def exchange_code(
        self, *, code: str, redirect_uri: str, code_verifier: str
    ) -> dict[str, Any]:
        settings = get_settings()
        meta = await self.discovery()
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "code_verifier": code_verifier,
        }
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(meta["token_endpoint"], data=token_data)
            if r.status_code != 200:
                raise AuthError("invalid_credentials", "token exchange failed")
            return r.json()  # type: ignore[no-any-return]

    async def verify_id_token(
        self, id_token: str, *, expected_nonce: str
    ) -> JWTClaims:
        settings = get_settings()
        meta = await self.discovery()
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(meta["jwks_uri"])
            r.raise_for_status()
            keys = r.json()
        try:
            claims = _jwt.decode(
                id_token,
                keys,
                claims_options={
                    "iss": {"essential": True, "values": ["https://accounts.google.com", "accounts.google.com"]},
                    "aud": {"essential": True, "value": settings.google_oauth_client_id},
                    "exp": {"essential": True},
                    "nonce": {"essential": True, "value": expected_nonce},
                },
            )
            claims.validate()
        except JoseError as exc:
            raise AuthError("invalid_credentials", "id_token validation failed") from exc
        return claims

    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """credentials must include: code, redirect_uri, code_verifier, nonce"""
        required = ("code", "redirect_uri", "code_verifier", "nonce")
        for k in required:
            if k not in credentials:
                raise AuthError("invalid_credentials", f"missing {k}")
        tokens = await self.exchange_code(
            code=credentials["code"],
            redirect_uri=credentials["redirect_uri"],
            code_verifier=credentials["code_verifier"],
        )
        id_token = tokens.get("id_token")
        if not id_token:
            raise AuthError("invalid_credentials", "no id_token from upstream")
        claims = await self.verify_id_token(id_token, expected_nonce=credentials["nonce"])
        email = claims.get("email")
        if not email or not claims.get("email_verified", True):
            raise AuthError("invalid_credentials", "email missing or unverified")
        return AuthResult(
            provider=self.name,
            external_id=str(claims.get("sub")),
            email=str(email).lower(),
            display_name=str(claims.get("name") or email),
            raw_claims=dict(claims),
        )
