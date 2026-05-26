"""Phase 5.2 / US1: admin endpoints for auto-tag rules (CRUD + reorder + test).

Contract: specs/014-auto-tag-rules/contracts/tag-rules.yaml
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.models import MatcherType, TagRule
from ai_api.services.tag_rules import TagRuleService, UnsafeRegexError

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _serialize(rule: TagRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "order_index": rule.order_index,
        "matcher_type": rule.matcher_type.value,
        "pattern": rule.pattern,
        "tag": rule.tag,
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat(),
        "created_by": rule.created_by,
    }


class CreateRuleRequest(BaseModel):
    matcher_type: MatcherType
    pattern: str = ""
    tag: str
    enabled: bool = True


class UpdateRuleRequest(BaseModel):
    matcher_type: MatcherType | None = None
    pattern: str | None = None
    tag: str | None = None
    enabled: bool | None = None


class ReorderRequest(BaseModel):
    order: list[str] = Field(min_length=0)


class TestRequest(BaseModel):
    email: EmailStr


@router.get("/tag-rules")
async def list_rules(session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    return [_serialize(r) for r in await TagRuleService(session).list_rules()]


@router.post("/tag-rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: CreateRuleRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    svc = TagRuleService(session)
    try:
        rule = await svc.create(
            matcher_type=payload.matcher_type,
            tag=payload.tag,
            pattern=payload.pattern,
            enabled=payload.enabled,
        )
    except UnsafeRegexError as exc:
        raise HTTPException(status_code=422, detail=_err("unsafe_regex", str(exc))) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_err("invalid_tag", str(exc))) from exc
    return _serialize(rule)


@router.patch("/tag-rules/{rule_id}")
async def update_rule(
    rule_id: str,
    payload: UpdateRuleRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    svc = TagRuleService(session)
    try:
        rule = await svc.update(
            rule_id,
            matcher_type=payload.matcher_type,
            pattern=payload.pattern,
            tag=payload.tag,
            enabled=payload.enabled,
        )
    except UnsafeRegexError as exc:
        raise HTTPException(status_code=422, detail=_err("unsafe_regex", str(exc))) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_err("invalid_tag", str(exc))) from exc
    if rule is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "rule not found"))
    return _serialize(rule)


@router.delete("/tag-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str, session: AsyncSession = Depends(get_db_session)
) -> None:
    if not await TagRuleService(session).delete(rule_id):
        raise HTTPException(status_code=404, detail=_err("not_found", "rule not found"))


@router.post("/tag-rules/reorder")
async def reorder_rules(
    payload: ReorderRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    result = await TagRuleService(session).reorder(payload.order)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=_err("order_mismatch", "order list must contain exactly the existing rule ids"),
        )
    return [_serialize(r) for r in result]


@router.post("/tag-rules/test")
async def test_rules(
    payload: TestRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    match = await TagRuleService(session).test_email(str(payload.email))
    mt = match["matcher_type"]
    return {
        "matched": match["matched"],
        "rule_id": match["rule_id"],
        "tag": match["tag"],
        "matcher_type": mt.value if mt is not None else None,
    }
