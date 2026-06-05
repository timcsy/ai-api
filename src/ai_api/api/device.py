"""Public device-flow endpoints (Phase 19) — called by the Codex install script.

No session: `POST /device/authorize` starts a request, `POST /device/token`
polls by device_code. RFC 8628-style: non-success polls return HTTP 400 with a
bare ``{"error": "..."}`` body (authorization_pending / slow_down / expired_token
/ access_denied); success returns the plaintext token once.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.services.device_flow import DeviceFlowService

router = APIRouter()


class AuthorizeRequest(BaseModel):
    device_label: str | None = None


class TokenRequest(BaseModel):
    device_code: str


@router.post("/device/authorize", status_code=status.HTTP_201_CREATED)
async def device_authorize(
    payload: AuthorizeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    res = await DeviceFlowService(db).authorize(payload.device_label)
    return {
        "device_code": res.device_code,
        "user_code": res.user_code,
        "verification_uri": res.verification_uri,
        "verification_uri_complete": res.verification_uri_complete,
        "expires_in": res.expires_in,
        "interval": res.interval,
    }


@router.post("/device/token", response_model=None)
async def device_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    res = await DeviceFlowService(db).poll(payload.device_code)
    if res.status == "success":
        return {
            "token": res.token,
            "token_prefix": res.token_prefix,
            "credential_id": res.credential_id,
        }
    if res.status == "not_found":
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "not_found"})
    # authorization_pending / slow_down / expired_token / access_denied
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": res.status})
