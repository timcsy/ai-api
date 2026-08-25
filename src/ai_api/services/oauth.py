"""OAuth 2.0 Authorization Code + PKCE — first-party web-app key provisioning.

Structurally a redirect-based sibling of the device flow (services/device_flow):
a logged-in member consents (picking allocations); an authorization `code` bound
to the PKCE `code_challenge` and `redirect_uri` is minted; the app exchanges it
(+ `code_verifier`) at /oauth/token for a long-lived Credential — the exact same
revocable, scoped, billed key the rest of the system issues. No client secret
(public clients / SPAs); PKCE + a redirect_uri allowlist are the defenses.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import Allocation, Credential, Member, OAuthAuthorization, OAuthAuthStatus
from ai_api.services.allocations import AllocationService
from ai_api.services.credentials import GeneratedToken


class OAuthError(Exception):
    """Bad request in the OAuth flow (maps to 400 with an `error` code)."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _b64url_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def allowed_redirect_uris(settings: object) -> list[str]:
    raw = getattr(settings, "oauth_redirect_allowlist", "") or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def validate_redirect_uri(redirect_uri: str, settings: object) -> None:
    """Fail-closed prefix allowlist — the critical anti-open-redirect defense."""
    prefixes = allowed_redirect_uris(settings)
    if not prefixes:
        raise OAuthError("redirect_uri_not_allowed", "no redirect_uri allowlist configured")
    if not any(redirect_uri.startswith(p) for p in prefixes):
        raise OAuthError("redirect_uri_not_allowed", "redirect_uri is not on the allowlist")


def verify_pkce_s256(code_verifier: str, code_challenge: str) -> bool:
    expected = _b64url_nopad(hashlib.sha256(code_verifier.encode("ascii")).digest())
    return hmac.compare_digest(expected, code_challenge)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class OAuthService:
    CONSENT_TTL = 600  # seconds a pending consent stays actionable
    CODE_TTL = 120     # seconds an approved authorization code is exchangeable

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create_consent(
        self,
        *,
        member: Member,
        client_name: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        state: str | None,
        scope: str | None,
        settings: object,
    ) -> OAuthAuthorization:
        validate_redirect_uri(redirect_uri, settings)
        if code_challenge_method != "S256":
            raise OAuthError("invalid_request", "only PKCE code_challenge_method=S256 is supported")
        if not code_challenge or len(code_challenge) < 43:
            raise OAuthError("invalid_request", "missing or malformed code_challenge")
        if not client_name.strip():
            raise OAuthError("invalid_request", "client_name is required")
        now = datetime.now(UTC)
        row = OAuthAuthorization(
            id=str(ULID()),
            client_name=client_name.strip()[:128],
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            member_id=member.id,
            status=OAuthAuthStatus.pending,
            created_at=now,
            expires_at=now + timedelta(seconds=self.CONSENT_TTL),
        )
        self._s.add(row)
        await self._s.flush()
        return row

    async def get_pending(self, auth_id: str, member: Member) -> OAuthAuthorization | None:
        row = await self._s.get(OAuthAuthorization, auth_id)
        if row is None or row.member_id != member.id:
            return None
        if row.status != OAuthAuthStatus.pending:
            return None
        if datetime.now(UTC) >= _aware(row.expires_at):
            row.status = OAuthAuthStatus.expired
            await self._s.flush()
            return None
        return row

    async def approve(
        self, auth_id: str, member: Member, allocation_ids: Sequence[str]
    ) -> OAuthAuthorization:
        """Approve consent → mint a short-lived authorization code. The Credential
        is NOT created yet (only on token exchange), so an intercepted-but-unused
        code never yields a live key."""
        row = await self.get_pending(auth_id, member)
        if row is None:
            raise OAuthError("not_found", "authorization not found, expired, or already used")
        if not allocation_ids:
            raise OAuthError("invalid_scope", "at least one allocation is required")
        # Ownership + scope validity are enforced by create_member_credential at
        # exchange time; validate ownership early for a clean consent-time error.
        owned = set(
            (
                await self._s.execute(
                    select(Allocation.id).where(Allocation.member_id == member.id)
                )
            ).scalars().all()
        )
        if any(a not in owned for a in allocation_ids):
            raise OAuthError("invalid_scope", "an allocation does not belong to you")
        now = datetime.now(UTC)
        row.allocation_ids = list(allocation_ids)
        row.code = secrets.token_urlsafe(32)
        row.status = OAuthAuthStatus.approved
        row.approved_at = now
        row.expires_at = now + timedelta(seconds=self.CODE_TTL)
        await self._s.flush()
        return row

    async def deny(self, auth_id: str, member: Member) -> OAuthAuthorization | None:
        row = await self.get_pending(auth_id, member)
        if row is None:
            return None
        row.status = OAuthAuthStatus.denied
        await self._s.flush()
        return row

    async def exchange(
        self, *, code: str, redirect_uri: str, code_verifier: str
    ) -> tuple[Credential, GeneratedToken, OAuthAuthorization]:
        """Exchange an authorization code (+ PKCE verifier) for a Credential.
        Single-use; binds to the same redirect_uri and PKCE challenge as consent."""
        row = (
            await self._s.execute(
                select(OAuthAuthorization).where(OAuthAuthorization.code == code)
            )
        ).scalar_one_or_none()
        if row is None or row.status != OAuthAuthStatus.approved:
            raise OAuthError("invalid_grant", "code not found or already used")
        if datetime.now(UTC) >= _aware(row.expires_at):
            row.status = OAuthAuthStatus.expired
            await self._s.flush()
            raise OAuthError("invalid_grant", "authorization code expired")
        if redirect_uri != row.redirect_uri:
            raise OAuthError("invalid_grant", "redirect_uri mismatch")
        if not verify_pkce_s256(code_verifier, row.code_challenge):
            raise OAuthError("invalid_grant", "PKCE verification failed")
        member = await self._s.get(Member, row.member_id)
        if member is None:
            raise OAuthError("invalid_grant", "member no longer exists")
        credential, token = await AllocationService(self._s).create_member_credential(
            row.member_id, row.client_name, row.allocation_ids or []
        )
        row.status = OAuthAuthStatus.consumed
        row.consumed_at = datetime.now(UTC)
        row.credential_id = credential.id
        await self._s.flush()
        return credential, token, row
