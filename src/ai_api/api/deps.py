"""Shared FastAPI dependencies."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.config import Settings, get_settings
from ai_api.db import get_sessionmaker

ADMIN_TOKEN_HEADER = "X-Admin-Token"


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
