"""Admin system info — read-only infra context (e.g. body size limit)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ai_api.api.deps import require_admin_token
from ai_api.config import get_settings

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("/system/info")
async def system_info() -> dict[str, Any]:
    settings = get_settings()
    return {
        "request_body_limit_mb": settings.request_body_limit_mb,
    }
