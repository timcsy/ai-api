"""Shared FastAPI dependencies."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Cookie, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.auth.sessions import SESSION_COOKIE_NAME, validate_session
from ai_api.config import Settings, get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import Member

ADMIN_TOKEN_HEADER = "X-Admin-Token"
CSRF_COOKIE = "aiapi_csrf"
CSRF_HEADER = "X-CSRF-Token"


async def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
) -> None:
    settings = get_settings()
    if not x_admin_token or x_admin_token != settings.admin_bootstrap_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "unauthorized",
                    "message": "missing or invalid admin token",
                }
            },
        )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_settings_dep() -> Settings:
    return get_settings()


async def current_member(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Member:
    """Resolve current Member from session cookie. 401 if not authenticated."""
    sm = get_sessionmaker()
    async with sm() as s:
        member = await validate_session(s, session_cookie or "")
        await s.commit()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "session required"}},
        )
    return member


async def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
) -> None:
    """Double-submit cookie CSRF protection for mutating member endpoints."""
    if not csrf_cookie or not x_csrf_token or csrf_cookie != x_csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "csrf_failed", "message": "CSRF check failed"}},
        )
