"""OAuth 2.0 Authorization Code + PKCE endpoints (first-party web apps).

Public:  POST /oauth/token            — exchange an authorization code for a key.
Session: POST /me/oauth/consent      — register a consent (validates redirect_uri)
         GET  /me/oauth/{id}         — consent details for the authorization page
         POST /me/oauth/{id}/approve — pick allocations → mint the code + redirect
         POST /me/oauth/{id}/deny    — decline

The issued `access_token` is the same revocable, scoped, billed Credential the
rest of the system uses; OAuth is only the provisioning UX. No client secret —
PKCE (S256) + a redirect_uri allowlist are the defenses.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import current_member, get_db_session, require_csrf
from ai_api.config import get_settings
from ai_api.models import Allocation, AllocationStatus, Member, ModelCatalog
from ai_api.services.oauth import OAuthError, OAuthService

router = APIRouter()


# ----------------------------------------------------------------- session side

class ConsentRequest(BaseModel):
    client_name: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str = "S256"
    state: str | None = None
    scope: str | None = None


class ApproveRequest(BaseModel):
    allocation_ids: list[str] = Field(min_length=1)


def _oauth_400(exc: OAuthError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": {"code": exc.code, "message": str(exc)}},
    )


@router.post("/me/oauth/consent", dependencies=[Depends(require_csrf)])
async def create_consent(
    payload: ConsentRequest,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Register an authorize request (validates redirect_uri against the allowlist
    and PKCE method) and return the info the consent page needs, incl. the
    member's allocations to grant."""
    try:
        row = await OAuthService(db).create_consent(
            member=member,
            client_name=payload.client_name,
            redirect_uri=payload.redirect_uri,
            code_challenge=payload.code_challenge,
            code_challenge_method=payload.code_challenge_method,
            state=payload.state,
            scope=payload.scope,
            settings=get_settings(),
        )
    except OAuthError as exc:
        raise _oauth_400(exc) from exc

    allocs = (
        await db.execute(
            select(Allocation.id, Allocation.resource_model)
            .where(Allocation.member_id == member.id, Allocation.status == AllocationStatus.active)
            .order_by(Allocation.created_at.desc())
        )
    ).all()
    name_rows = (await db.execute(select(ModelCatalog.slug, ModelCatalog.display_name))).all()
    names: dict[str, str] = {row[0]: row[1] for row in name_rows}
    return {
        "id": row.id,
        "client_name": row.client_name,
        "redirect_uri": row.redirect_uri,
        "scope": row.scope,
        "allocations": [
            {"id": aid, "resource_model": model, "display_name": names.get(model)}
            for aid, model in allocs
        ],
    }


@router.get("/me/oauth/{auth_id}")
async def get_consent(
    auth_id: str,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await OAuthService(db).get_pending(auth_id, member)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "authorization not found or expired"}},
        )
    return {
        "id": row.id,
        "client_name": row.client_name,
        "redirect_uri": row.redirect_uri,
        "scope": row.scope,
    }


@router.post("/me/oauth/{auth_id}/approve", dependencies=[Depends(require_csrf)])
async def approve_consent(
    auth_id: str,
    payload: ApproveRequest,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Approve → mint the authorization code. Returns the redirect target the SPA
    should send the browser to (code + echoed state)."""
    try:
        row = await OAuthService(db).approve(auth_id, member, payload.allocation_ids)
    except OAuthError as exc:
        if exc.code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "not_found", "message": str(exc)}},
            ) from exc
        raise _oauth_400(exc) from exc
    return {"redirect_uri": row.redirect_uri, "code": row.code, "state": row.state}


@router.post("/me/oauth/{auth_id}/deny", dependencies=[Depends(require_csrf)])
async def deny_consent(
    auth_id: str,
    member: Member = Depends(current_member),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await OAuthService(db).deny(auth_id, member)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "authorization not found or expired"}},
        )
    return {"redirect_uri": row.redirect_uri, "error": "access_denied", "state": row.state}


# ------------------------------------------------------------------ public side

class TokenRequest(BaseModel):
    grant_type: str = "authorization_code"
    code: str
    redirect_uri: str
    code_verifier: str


@router.post("/oauth/token", response_model=None)
async def oauth_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Public token exchange (no session). PKCE + single-use code + redirect_uri
    binding are the checks. Returns the plaintext key once."""
    if payload.grant_type != "authorization_code":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "unsupported_grant_type", "message": payload.grant_type}},
        )
    try:
        credential, token, row = await OAuthService(db).exchange(
            code=payload.code,
            redirect_uri=payload.redirect_uri,
            code_verifier=payload.code_verifier,
        )
    except OAuthError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
    return {
        "access_token": token.plaintext,
        "token_type": "bearer",
        "credential_id": credential.id,
        "scope": row.scope,
    }
