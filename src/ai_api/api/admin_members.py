"""Admin member management endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.auth.sessions import revoke_all_for_member
from ai_api.models import Member, MemberProvider, MemberStatus, Session
from ai_api.services.members import (
    LastAdminCannotDemoteError,
    MemberAlreadyExists,
    MemberHasActiveAllocations,
    MemberService,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


class CreateMemberRequest(BaseModel):
    email: EmailStr
    provider: MemberProvider
    display_name: str | None = None
    external_id: str | None = None
    initial_password: str | None = None
    send_invitation: bool = True


class UpdateMemberRequest(BaseModel):
    display_name: str | None = None
    status: MemberStatus | None = None
    is_admin: bool | None = None


def _member_admin(m: Member) -> dict[str, Any]:
    return {
        "id": m.id,
        "email": m.email,
        "provider": m.provider,
        "external_id": m.external_id,
        "display_name": m.display_name,
        "status": m.status,
        "created_at": m.created_at.isoformat(),
        "disabled_at": m.disabled_at.isoformat() if m.disabled_at else None,
        "created_by": m.created_by,
        "has_password": m.password_hash is not None,
        "is_admin": m.is_admin,
    }


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def create_member(
    request: Request,
    payload: CreateMemberRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = MemberService(session)
    try:
        created = await service.create(
            email=payload.email,
            provider=payload.provider,
            display_name=payload.display_name,
            external_id=payload.external_id,
            initial_password=payload.initial_password,
            send_invitation=payload.send_invitation,
        )
    except MemberAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "member_exists", "message": str(exc)}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": str(exc)}},
        ) from exc

    body = _member_admin(created.member)
    if created.invitation_plaintext is not None:
        base_url = str(request.base_url).rstrip("/")
        body["invitation_url"] = f"{base_url}/auth/invitation/{created.invitation_plaintext}"
    return body


@router.get("/members")
async def list_members(
    provider: MemberProvider | None = Query(default=None),
    status_q: MemberStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    members = await MemberService(session).list(provider=provider, status=status_q, q=q)
    return [_member_admin(m) for m in members]


@router.get("/members/{member_id}")
async def get_member(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    member = await MemberService(session).get(member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )
    return _member_admin(member)


@router.patch("/members/{member_id}")
async def update_member(
    member_id: str,
    payload: UpdateMemberRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = MemberService(session)
    member = await service.update(
        member_id, display_name=payload.display_name, status=payload.status
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )
    if payload.is_admin is not None:
        try:
            member = await service.set_is_admin(member_id, payload.is_admin)
        except LastAdminCannotDemoteError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "last_admin_cannot_demote",
                        "message": "at least one active admin must remain",
                    }
                },
            ) from exc
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "not_found", "message": "member not found"}},
            )
    return _member_admin(member)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        ok = await MemberService(session).delete(member_id)
    except MemberHasActiveAllocations as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "member_has_allocations",
                    "message": "revoke and delete allocations before deleting member",
                }
            },
        ) from exc
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )


@router.get("/members/{member_id}/sessions")
async def list_member_sessions(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    member = await MemberService(session).get(member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )
    rows = (
        await session.execute(
            select(Session)
            .where(Session.member_id == member_id)
            .order_by(Session.last_seen_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": s.id,
            "member_id": s.member_id,
            "created_at": s.created_at.isoformat(),
            "last_seen_at": s.last_seen_at.isoformat(),
            "expires_at": s.expires_at.isoformat(),
            "source_ip": s.source_ip,
            "user_agent": s.user_agent,
            "status": s.status,
        }
        for s in rows
    ]


@router.delete("/members/{member_id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_member_sessions(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await revoke_all_for_member(session, member_id, reason="manual")
