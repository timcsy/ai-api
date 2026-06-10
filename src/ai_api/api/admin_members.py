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
    CannotDeleteSelfError,
    LastAdminCannotDeleteError,
    LastAdminCannotDemoteError,
    MemberAlreadyExists,
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


class BulkDeleteRequest(BaseModel):
    member_ids: list[str]


class BulkCreateRequest(BaseModel):
    emails: str  # newline-separated email list


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
    current_admin: Member | None = Depends(require_admin_token),
) -> None:
    try:
        ok = await MemberService(session).delete(
            member_id, acting_admin_id=current_admin.id if current_admin else None
        )
    except CannotDeleteSelfError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {"code": "cannot_delete_self", "message": "cannot delete your own account"}
            },
        ) from exc
    except LastAdminCannotDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {"code": "last_admin", "message": "at least one active admin must remain"}
            },
        ) from exc
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "member not found"}},
        )


@router.post("/members/bulk-delete")
async def bulk_delete_members(
    payload: BulkDeleteRequest,
    current_admin: Member | None = Depends(require_admin_token),
) -> dict[str, Any]:
    """Batch safe-delete. Each id is processed in its own transaction; one
    failure never rolls back or blocks the others (per-item independent)."""
    if not payload.member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "member_ids must not be empty"}},
        )
    from ai_api.db import get_sessionmaker

    acting_id = current_admin.id if current_admin else None
    sm = get_sessionmaker()
    results: list[dict[str, Any]] = []
    deleted = failed = 0
    for mid in payload.member_ids:
        reason: str | None = None
        try:
            async with sm() as s:
                ok = await MemberService(s).delete(mid, acting_admin_id=acting_id)
                await s.commit()
            if ok:
                results.append({"member_id": mid, "status": "deleted", "reason": None})
                deleted += 1
                continue
            reason = "not_found"
        except CannotDeleteSelfError:
            reason = "cannot_delete_self"
        except LastAdminCannotDeleteError:
            reason = "last_admin"
        except Exception:
            reason = "internal"
        results.append({"member_id": mid, "status": "failed", "reason": reason})
        failed += 1
    return {"deleted": deleted, "failed": failed, "results": results}


@router.post("/members/bulk-create")
async def bulk_create_members(
    request: Request,
    payload: BulkCreateRequest,
) -> dict[str, Any]:
    """Batch pre-create local_password members from a pasted email list. Each
    email is processed independently; results are classified created / exists /
    invalid / duplicate."""
    from pydantic import TypeAdapter

    from ai_api.db import get_sessionmaker

    email_adapter: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)
    lines = [ln.strip().lower() for ln in payload.emails.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "no emails provided"}},
        )

    base_url = str(request.base_url).rstrip("/")
    sm = get_sessionmaker()
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    counts = {"created": 0, "exists": 0, "invalid": 0, "duplicate": 0}

    for email in lines:
        if email in seen:
            results.append({"email": email, "status": "duplicate", "invitation_url": None})
            counts["duplicate"] += 1
            continue
        seen.add(email)
        try:
            email_adapter.validate_python(email)
        except Exception:
            results.append({"email": email, "status": "invalid", "invitation_url": None})
            counts["invalid"] += 1
            continue
        try:
            async with sm() as s:
                created = await MemberService(s).create(
                    email=email,
                    provider=MemberProvider.local_password,
                    send_invitation=True,
                    created_by="bulk-admin",
                )
                from ai_api.auth import audit
                from ai_api.models import ActorType, AuditEventType

                await audit.record(
                    s,
                    event_type=AuditEventType.member_created,
                    actor_type=ActorType.admin,
                    actor_id="bulk-admin",
                    target_type="member",
                    target_id=created.member.id,
                )
                invitation_url = (
                    f"{base_url}/auth/invitation/{created.invitation_plaintext}"
                    if created.invitation_plaintext
                    else None
                )
                await s.commit()
            results.append({"email": email, "status": "created", "invitation_url": invitation_url})
            counts["created"] += 1
        except MemberAlreadyExists:
            results.append({"email": email, "status": "exists", "invitation_url": None})
            counts["exists"] += 1
    return {**counts, "results": results}


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
