"""Auth endpoints: /auth/oidc/*, /auth/local/login, /auth/logout, /auth/invitation/*."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.api.deps import (
    CSRF_COOKIE,
    get_db_session,
)
from ai_api.auth import audit, local, policy, sessions
from ai_api.auth.base import AuthError
from ai_api.auth.google_oidc import GoogleOidcProvider
from ai_api.auth.invitations import consume as consume_invite
from ai_api.auth.invitations import lookup as lookup_invite
from ai_api.auth.ratelimit import (
    is_ip_locked,
    is_locked,
    record_attempt,
)
from ai_api.config import get_settings
from ai_api.models import (
    ActorType,
    AttemptOutcome,
    AuditEventType,
    Member,
    MemberProvider,
    MemberStatus,
    OidcState,
)

router = APIRouter()

_INVITATION_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Set your password</title></head>
<body>
<h1>Set your password</h1>
<p>Token: {token_prefix}…</p>
<form method="post" action="/auth/invitation/{token}">
  <label>Password (≥ 10 chars):
    <input name="password" type="password" minlength="10" required />
  </label>
  <button type="submit">Set password</button>
</form>
<p style="color:#666">This page can also accept JSON via the same URL.</p>
</body></html>
"""

_INVITATION_INVALID_HTML = (
    "<!doctype html><html><body><h1>Invitation invalid or expired</h1>"
    "<p>Please contact your administrator for a new invitation.</p></body></html>"
)


def _set_session_cookie(response: Response, plaintext: str) -> None:
    settings = get_settings()
    # Phase 3a FR-016: cross-origin SPAs require SameSite=None + Secure.
    cors_enabled = bool(settings.cors_origins)
    samesite: Literal["lax", "none"] = "none" if cors_enabled else "lax"
    secure = True if cors_enabled else settings.cookie_secure
    response.set_cookie(
        key=sessions.SESSION_COOKIE_NAME,
        value=plaintext,
        max_age=int(sessions.DEFAULT_LIFETIME.total_seconds()),
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )
    csrf = ULID().hex[:32]
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf,
        max_age=int(sessions.DEFAULT_LIFETIME.total_seconds()),
        httponly=False,  # JS reads to echo into X-CSRF-Token
        secure=secure,
        samesite=samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(sessions.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _client_ip(request: Request) -> str | None:
    return (
        request.client.host
        if request.client is not None
        else request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or None
    )


def _error_response(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message}},
    )


# ============== OIDC ==============


@router.get("/auth/oidc/start")
async def oidc_start(
    request: Request,
    next: str = "/me",
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    if not settings.google_oauth_client_id:
        return _error_response("provider_not_configured", "Google OIDC not configured", 503)
    # Source restriction
    ip = _client_ip(request)
    if not await policy.is_source_allowed(session, ip):
        return _error_response("source_not_allowed", "this source is not allowed", 401)
    if not next.startswith("/"):
        next = "/me"
    provider = GoogleOidcProvider()
    redirect_uri = f"{settings.base_url.rstrip('/')}/auth/oidc/callback"
    info = await provider.build_authorize_url(redirect_uri=redirect_uri)
    session.add(
        OidcState(
            state=info.state,
            nonce=info.nonce,
            code_verifier=info.code_verifier,
            redirect_to=next,
            created_at=datetime.now(UTC),
            expires_at=info.expires_at,
        )
    )
    await session.flush()
    return RedirectResponse(url=info.url, status_code=302)


@router.get("/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    state_row = await session.get(OidcState, state)
    if state_row is None:
        return _error_response("invalid_state", "state expired or invalid", 401)
    _exp = state_row.expires_at if state_row.expires_at.tzinfo else state_row.expires_at.replace(tzinfo=UTC)
    if _exp <= datetime.now(UTC):
        return _error_response("invalid_state", "state expired or invalid", 401)
    # Capture attributes before deletion (SQLA may expire them post-flush).
    redirect_to = state_row.redirect_to
    code_verifier = state_row.code_verifier
    nonce = state_row.nonce
    await session.delete(state_row)
    await session.flush()

    provider = GoogleOidcProvider()
    try:
        result = await provider.authenticate(
            {
                "code": code,
                "redirect_uri": f"{settings.base_url.rstrip('/')}/auth/oidc/callback",
                "code_verifier": code_verifier,
                "nonce": nonce,
            }
        )
    except AuthError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "oidc auth failed code=%s message=%s", exc.code, exc.message
        )
        await audit.record(
            session,
            event_type=AuditEventType.login_failure,
            actor_type=ActorType.anonymous,
            source_ip=_client_ip(request),
            details={"reason": exc.code, "stage": "oidc", "message": exc.message},
        )
        return _error_response("invalid_credentials", "auth failed", 401)

    # policy gate
    if not await policy.is_email_allowed(session, result.email):
        await audit.record(
            session,
            event_type=AuditEventType.login_failure,
            actor_type=ActorType.anonymous,
            source_ip=_client_ip(request),
            details={"reason": "not_allowed", "email": result.email},
        )
        return _error_response("not_allowed", "this account is not authorised on this platform", 401)

    member = await _find_or_create_oidc_member(session, result)
    if member.status != MemberStatus.active:
        return _error_response("disabled", "account disabled", 401)

    issued = await sessions.create_session(
        session,
        member.id,
        source_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await audit.record(
        session,
        event_type=AuditEventType.login_success,
        actor_type=ActorType.member,
        actor_id=member.id,
        source_ip=_client_ip(request),
        details={"provider": "google_oidc"},
    )
    response = RedirectResponse(url=redirect_to, status_code=302)
    _set_session_cookie(response, issued.plaintext)
    return response


async def _find_or_create_oidc_member(
    session: AsyncSession, result: Any
) -> Member:
    existing = (
        await session.execute(
            select(Member).where(Member.email == result.email)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.provider != MemberProvider.google_oidc:
            # Conflict: email belongs to another provider — refuse to bind.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "provider_conflict", "message": "email bound to a different provider"}},
            )
        return existing
    new = Member(
        id=str(ULID()),
        email=result.email,
        provider=MemberProvider.google_oidc,
        external_id=result.external_id,
        display_name=result.display_name,
        status=MemberStatus.active,
        password_hash=None,
        created_at=datetime.now(UTC),
        disabled_at=None,
        created_by="auto_register",
    )
    session.add(new)
    await session.flush()
    return new


# ============== LOCAL ==============


class LocalLoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/local/login")
async def local_login(
    request: Request,
    payload: LocalLoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    email = str(payload.email).lower()
    ip = _client_ip(request)
    if not await policy.is_source_allowed(session, ip):
        return _error_response("source_not_allowed", "this source is not allowed", 401)
    if await is_ip_locked(session, ip):
        return _error_response("rate_limited", "too many attempts from this source", 429)
    if await is_locked(session, email):
        return _error_response("rate_limited", "too many attempts; try again later", 429)

    member = (
        await session.execute(select(Member).where(Member.email == email))
    ).scalar_one_or_none()
    if member is None:
        await record_attempt(session, email, AttemptOutcome.unknown_email, source_ip=ip)
        await audit.record(
            session,
            event_type=AuditEventType.login_failure,
            actor_type=ActorType.anonymous,
            source_ip=ip,
            details={"reason": "unknown_email", "email": email},
        )
        return _error_response("invalid_credentials", "invalid email or password", 401)

    if member.provider != MemberProvider.local_password or member.password_hash is None:
        await record_attempt(session, email, AttemptOutcome.bad_password, source_ip=ip)
        return _error_response("invalid_credentials", "invalid email or password", 401)

    if member.status != MemberStatus.active:
        await record_attempt(session, email, AttemptOutcome.disabled, source_ip=ip)
        return _error_response("invalid_credentials", "invalid email or password", 401)

    if not local.verify_password(member.password_hash, payload.password):
        await record_attempt(session, email, AttemptOutcome.bad_password, source_ip=ip)
        await audit.record(
            session,
            event_type=AuditEventType.login_failure,
            actor_type=ActorType.member,
            actor_id=member.id,
            source_ip=ip,
            details={"reason": "bad_password", "email": email},
        )
        return _error_response("invalid_credentials", "invalid email or password", 401)

    await record_attempt(session, email, AttemptOutcome.success, source_ip=ip)
    issued = await sessions.create_session(
        session,
        member.id,
        source_ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await audit.record(
        session,
        event_type=AuditEventType.login_success,
        actor_type=ActorType.member,
        actor_id=member.id,
        source_ip=ip,
        details={"provider": "local_password"},
    )
    body = {
        "id": member.id,
        "email": member.email,
        "provider": member.provider,
        "display_name": member.display_name,
        "status": member.status,
    }
    response = JSONResponse(content=body)
    _set_session_cookie(response, issued.plaintext)
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session_cookie: str | None = Cookie(default=None, alias=sessions.SESSION_COOKIE_NAME),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    if session_cookie:
        await sessions.revoke_session(session, session_cookie, reason="logout")
    response = Response(status_code=204)
    _clear_session_cookie(response)
    return response


# ============== INVITATION ==============


class SetPasswordRequest(BaseModel):
    password: str


@router.get("/auth/invitation/{token}", response_class=HTMLResponse)
async def invitation_view(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    record = await lookup_invite(session, token)
    if record is None or record.used_at is not None:
        return HTMLResponse(_INVITATION_INVALID_HTML, status_code=404)
    _exp = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=UTC)
    if _exp <= datetime.now(UTC):
        return HTMLResponse(_INVITATION_INVALID_HTML, status_code=404)
    return HTMLResponse(
        _INVITATION_HTML.format(token=token, token_prefix=record.token_prefix)
    )


@router.post("/auth/invitation/{token}")
async def invitation_accept(
    request: Request,
    token: str,
    payload: SetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        local.enforce_policy(payload.password)
    except ValueError as exc:
        return _error_response("weak_password", str(exc), 400)

    member = await consume_invite(session, token)
    if member is None:
        return _error_response("invalid_token", "invitation invalid or expired", 404)

    member.password_hash = local.hash_password(payload.password)
    await session.flush()
    await audit.record(
        session,
        event_type=AuditEventType.invitation_used,
        actor_type=ActorType.member,
        actor_id=member.id,
        source_ip=_client_ip(request),
    )

    issued = await sessions.create_session(
        session,
        member.id,
        source_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    body = {
        "id": member.id,
        "email": member.email,
        "provider": member.provider,
        "display_name": member.display_name,
        "status": member.status,
    }
    response = JSONResponse(content=body)
    _set_session_cookie(response, issued.plaintext)
    return response
