"""Admin OAuth settings — edit the redirect_uri allowlist at runtime.

Singleton config (lazy-seeded from OAUTH_REDIRECT_ALLOWLIST); the DB row is the
source of truth once written. The allowlist is the anti-open-redirect defense,
so this is admin-only.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.models import Member
from ai_api.services.oauth import get_oauth_config, parse_allowlist

router = APIRouter(dependencies=[Depends(require_admin_token)])


class OAuthConfigUpdate(BaseModel):
    # Comma- or newline-separated redirect_uri prefixes. "" ⇒ OAuth refused
    # (fail-closed) — an explicit way to disable first-party OAuth.
    redirect_allowlist: str


def _serialize(cfg: Any) -> dict[str, Any]:
    return {
        "redirect_allowlist": cfg.redirect_allowlist,
        "prefixes": parse_allowlist(cfg.redirect_allowlist),
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        "updated_by": cfg.updated_by,
    }


@router.get("/oauth/config")
async def get_config(session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return _serialize(await get_oauth_config(session))


@router.put("/oauth/config")
async def update_config(
    body: OAuthConfigUpdate = Body(...),
    session: AsyncSession = Depends(get_db_session),
    admin: Member | None = Depends(require_admin_token),
) -> dict[str, Any]:
    cfg = await get_oauth_config(session)
    cfg.redirect_allowlist = body.redirect_allowlist
    cfg.updated_at = datetime.now(UTC)
    cfg.updated_by = admin.id if admin else "admin"
    await session.flush()
    return _serialize(cfg)
