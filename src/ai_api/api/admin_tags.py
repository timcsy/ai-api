"""Phase 5 US3: admin endpoints for Tag CRUD + per-member tags + bulk-apply.

Contract: specs/012-multi-provider-access/contracts/tags.yaml
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.services.member_tags import MemberTagService

router = APIRouter(dependencies=[Depends(require_admin_token)])


class AddTagsRequest(BaseModel):
    tags: list[str] = Field(min_length=1)


class BulkApplyRequest(BaseModel):
    tag: str
    member_ids: list[str] = Field(min_length=1)


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


_KNOWN_TAGS: set[str] = set()
# NOTE: in-memory registry — lost on restart and not shared across replicas.
# For org-internal single-replica deployments this is acceptable. If multi-
# replica or persistent vocabulary becomes required, persist via a dedicated
# `Tag` table (experience.md tag-design lesson covers the upgrade path).


@router.get("/tags")
async def list_tags(session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    rows = await MemberTagService(session).list_distinct()
    used = {r.tag: r.member_count for r in rows}
    # Merge with admin-registered empty tags (member_count=0)
    for empty_tag in _KNOWN_TAGS - used.keys():
        used[empty_tag] = 0
    return sorted(
        ({"tag": tag, "member_count": cnt} for tag, cnt in used.items()),
        key=lambda x: x["tag"],
    )


class CreateTagRequest(BaseModel):
    tag: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")


@router.post("/tags", status_code=status.HTTP_201_CREATED)
async def create_tag(payload: CreateTagRequest = Body(...)) -> dict[str, Any]:
    """Register a tag without assigning to any member yet (useful for tag-first
    workflow: define vocabulary → set model access → then assign to members)."""
    _KNOWN_TAGS.add(payload.tag)
    return {"tag": payload.tag, "member_count": 0}


@router.delete("/tags/{tag}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag: str, session: AsyncSession = Depends(get_db_session)
) -> None:
    cnt = await MemberTagService(session).delete_tag_globally(tag)
    if cnt == 0:
        raise HTTPException(status_code=404, detail=_err("not_found", f"tag '{tag}' not in use"))


@router.get("/members/{member_id}/tags")
async def list_member_tags(
    member_id: str, session: AsyncSession = Depends(get_db_session)
) -> list[str]:
    from ai_api.models import Member
    if (await session.get(Member, member_id)) is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "member not found"))
    return await MemberTagService(session).list_for_member(member_id)


@router.get("/members/{member_id}/tags/detail")
async def list_member_tags_detail(
    member_id: str, session: AsyncSession = Depends(get_db_session)
) -> list[dict[str, Any]]:
    """Tags with source metadata (manual/auto + rule_id). Separate from the plain
    `/tags` endpoint so existing consumers keep their `list[str]` shape."""
    from ai_api.models import Member
    if (await session.get(Member, member_id)) is None:
        raise HTTPException(status_code=404, detail=_err("not_found", "member not found"))
    rows = await MemberTagService(session).list_for_member_detail(member_id)
    return [
        {"tag": r.tag, "source": r.source.value, "rule_id": r.rule_id}
        for r in rows
    ]


@router.post("/members/{member_id}/tags")
async def add_member_tags(
    member_id: str,
    payload: AddTagsRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[str]:
    try:
        return await MemberTagService(session).add(member_id, payload.tags)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_err("not_found", str(exc))) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_err("invalid_tag", str(exc))) from exc


@router.delete("/members/{member_id}/tags", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member_tags(
    member_id: str,
    tag: list[str] = Query(default=[]),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    if not tag:
        raise HTTPException(
            status_code=422, detail=_err("invalid_request", "at least one tag query param required")
        )
    try:
        await MemberTagService(session).remove(member_id, tag)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_err("not_found", str(exc))) from exc


@router.post("/tags/bulk-apply")
async def bulk_apply_tag(
    payload: BulkApplyRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = MemberTagService(session)
    try:
        applied, skipped = await service.bulk_apply(payload.tag, payload.member_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_err("invalid_tag", str(exc))) from exc
    return {"tag": payload.tag, "applied_count": applied, "skipped_count": skipped}
