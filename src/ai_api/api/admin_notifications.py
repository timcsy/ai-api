"""Phase 13: /admin/notifications endpoints (config CRUD + test-send + history).

Contract: specs/022-admin-email-notifications/contracts/admin-notifications.openapi.yaml
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.services.notifications import (
    NotificationConfigService,
    NotificationConfigValidationError,
)
from ai_api.services.notifier_email import EmailNotifier

router = APIRouter(dependencies=[Depends(require_admin_token)])


# ---------- schemas ----------

class NotificationConfigCreate(BaseModel):
    smtp_host: str = Field(..., min_length=1, max_length=255)
    smtp_port: int = Field(..., ge=1, le=65535)
    smtp_username: str = Field(..., min_length=1, max_length=255)
    smtp_password: str = Field(..., min_length=1, max_length=256)
    sender_email: EmailStr
    sender_name: str = Field(default="AI API Manager", max_length=128)
    recipients: list[EmailStr] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("smtp_host")
    @classmethod
    def _host_no_whitespace(cls, v: str) -> str:
        if v != v.strip() or not v.strip():
            raise ValueError("smtp_host must be non-empty and contain no leading/trailing whitespace")
        return v


class TestSendRequest(BaseModel):
    test_recipient: EmailStr


# ---------- helpers ----------

def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


_AIOSMTPLIB_ERR_HINTS = {
    "auth": "驗證失敗：請檢查 SMTP 帳號 / 密碼是否正確（Gmail 需使用 App Password 而非帳號密碼）",
    "connect": "無法連線到 SMTP 伺服器：請檢查 host / port 是否正確、網路是否可達",
    "sender": "寄件者被伺服器拒絕：請確認 sender_email 是否獲授權寄送",
    "recipient": "收件人被伺服器拒絕：請確認 test_recipient 信箱存在且可接收",
    "unknown": "未知錯誤",
}


def _outcome_to_message(outcome: str, test_recipient: str) -> str:
    if outcome == "test_sent":
        return f"測試信已寄出至 {test_recipient}，請於 30 秒內查收。"
    for key, hint in _AIOSMTPLIB_ERR_HINTS.items():
        if key in outcome:
            return hint
    return _AIOSMTPLIB_ERR_HINTS["unknown"]


# ---------- endpoints ----------

@router.get("/config")
async def get_config(
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    cfg = await NotificationConfigService(session).get()
    if cfg is None:
        return Response(status_code=204)
    from fastapi.responses import JSONResponse
    return JSONResponse(content=NotificationConfigService.to_response(cfg))


@router.put("/config")
async def save_config(
    payload: NotificationConfigCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    svc = NotificationConfigService(session)
    try:
        cfg = await svc.save(
            smtp_host=payload.smtp_host,
            smtp_port=payload.smtp_port,
            smtp_username=payload.smtp_username,
            smtp_password=payload.smtp_password,
            sender_email=str(payload.sender_email),
            sender_name=payload.sender_name,
            recipients=[str(r) for r in payload.recipients],
            enabled=payload.enabled,
        )
    except NotificationConfigValidationError as exc:
        raise HTTPException(status_code=400, detail=_err("validation_error", str(exc))) from exc
    return NotificationConfigService.to_response(cfg)


@router.delete("/config", status_code=204)
async def delete_config(
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await NotificationConfigService(session).delete()
    return Response(status_code=204)


@router.post("/test-send")
async def test_send(
    payload: TestSendRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    svc = NotificationConfigService(session)
    cfg = await svc.get()
    if cfg is None:
        raise HTTPException(
            status_code=400,
            detail=_err(
                "no_config",
                "通知設定尚未建立，請先在「設定」區塊填妥 SMTP 資訊後再發送測試信",
            ),
        )
    notifier = EmailNotifier()
    try:
        result = await notifier.test_send(session=session, test_recipient=str(payload.test_recipient))
    except ValueError as exc:
        # Defensive — get() already returned cfg so this is unexpected
        raise HTTPException(
            status_code=400, detail=_err("no_config", str(exc))
        ) from exc

    outcome_value = result.outcome.value
    # Map service-layer (test_*) outcomes to OpenAPI contract enum (success / send_failed_*).
    if outcome_value == "test_sent":
        api_outcome = "success"
    elif outcome_value.startswith("test_failed_"):
        api_outcome = "send_failed_" + outcome_value[len("test_failed_") :]
    else:
        api_outcome = outcome_value
    return {
        "outcome": api_outcome,
        "message": _outcome_to_message(outcome_value, str(payload.test_recipient)),
        "smtp_response_code": result.smtp_response_code,
        "latency_ms": result.latency_ms,
    }


@router.get("/history")
async def list_history(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    rows, next_cursor = await NotificationConfigService(session).list_history(
        limit=limit, cursor=cursor, event_type=event_type, outcome=outcome
    )
    return {"rows": rows, "next_cursor": next_cursor}


# ---------- helpers exposed for tests ----------

_VALID_HOST = re.compile(r"^[A-Za-z0-9.\-]+$")
