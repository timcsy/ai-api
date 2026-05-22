"""Admin access control endpoints: whitelist / rules / source restrictions."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.models import RuleType
from ai_api.services.access_control import (
    RuleService,
    SourceRestrictionService,
    WhitelistService,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


# --- whitelist ---
class AddWhitelistRequest(BaseModel):
    email: EmailStr
    note: str | None = None


@router.get("/whitelist")
async def list_whitelist(session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    items = await WhitelistService(session).list()
    return [
        {
            "email": e.email,
            "added_at": e.added_at.isoformat(),
            "added_by": e.added_by,
            "note": e.note,
        }
        for e in items
    ]


@router.post("/whitelist", status_code=status.HTTP_201_CREATED)
async def add_whitelist(
    payload: AddWhitelistRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    entry = await WhitelistService(session).add(
        payload.email, added_by="bootstrap-admin", note=payload.note
    )
    return {
        "email": entry.email,
        "added_at": entry.added_at.isoformat(),
        "added_by": entry.added_by,
        "note": entry.note,
    }


@router.delete("/whitelist/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_whitelist(
    email: str, session: AsyncSession = Depends(get_db_session)
) -> None:
    ok = await WhitelistService(session).remove(email)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "not in whitelist"}},
        )


# --- rules ---
class CreateRuleRequest(BaseModel):
    rule_type: RuleType
    pattern: str
    enabled: bool = True
    note: str | None = None


@router.get("/rules")
async def list_rules(session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    items = await RuleService(session).list()
    return [
        {
            "id": r.id,
            "rule_type": r.rule_type,
            "pattern": r.pattern,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat(),
            "created_by": r.created_by,
            "note": r.note,
        }
        for r in items
    ]


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: CreateRuleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    rule = await RuleService(session).create(
        rule_type=payload.rule_type,
        pattern=payload.pattern,
        enabled=payload.enabled,
        created_by="bootstrap-admin",
        note=payload.note,
    )
    return {
        "id": rule.id,
        "rule_type": rule.rule_type,
        "pattern": rule.pattern,
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat(),
        "created_by": rule.created_by,
        "note": rule.note,
    }


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: str, session: AsyncSession = Depends(get_db_session)) -> None:
    ok = await RuleService(session).delete(rule_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "rule not found"}},
        )


# --- source restrictions ---
class CreateSourceRestrictionRequest(BaseModel):
    cidr: str
    enabled: bool = True
    note: str | None = None


@router.get("/source-restrictions")
async def list_source_restrictions(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    items = await SourceRestrictionService(session).list()
    return [
        {
            "id": r.id,
            "cidr": r.cidr,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat(),
            "created_by": r.created_by,
            "note": r.note,
        }
        for r in items
    ]


@router.post("/source-restrictions", status_code=status.HTTP_201_CREATED)
async def create_source_restriction(
    payload: CreateSourceRestrictionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await SourceRestrictionService(session).create(
        cidr=payload.cidr,
        enabled=payload.enabled,
        created_by="bootstrap-admin",
        note=payload.note,
    )
    return {
        "id": item.id,
        "cidr": item.cidr,
        "enabled": item.enabled,
        "created_at": item.created_at.isoformat(),
        "created_by": item.created_by,
        "note": item.note,
    }


@router.delete("/source-restrictions/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_restriction(
    item_id: str, session: AsyncSession = Depends(get_db_session)
) -> None:
    ok = await SourceRestrictionService(session).delete(item_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "restriction not found"}},
        )
