"""Admin governance of application credentials (Phase 20).

Admin can view any member's application keys and revoke / adjust their scope.
Member self-service lives in `me.py`; this is the admin authority path.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session, require_admin_token
from ai_api.api.schemas import AllocationRef, AppCredentialOut, ScopePatchRequest
from ai_api.services.allocations import AllocationService

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _app_cred_out(c: Any) -> AppCredentialOut:
    return AppCredentialOut(
        id=c.id,
        name=c.name,
        token_prefix=c.token_prefix,
        created_at=c.created_at,
        last_used_at=c.last_used_at,
        status="revoked" if c.revoked_at else "active",
        allocations=[
            AllocationRef(
                allocation_id=a.id,
                resource_model=a.resource_model,
                display_name=None,
                status=str(a.status),
            )
            for a in c.allocations
        ],
    )


@router.get("/members/{member_id}/credentials", response_model=list[AppCredentialOut])
async def admin_list_member_credentials(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[AppCredentialOut]:
    creds = await AllocationService(session).list_member_credentials(member_id)
    return [_app_cred_out(c) for c in creds]


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_revoke_credential(
    credential_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    from ai_api.auth import audit
    from ai_api.models import ActorType, AuditEventType

    service = AllocationService(session)
    cred = await service.get_credential(credential_id)
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "credential not found"}},
        )
    await service.revoke_credential(credential_id)
    await audit.record(
        session,
        event_type=AuditEventType.credential_revoked,
        actor_type=ActorType.admin,
        target_type="credential",
        target_id=credential_id,
    )


@router.patch("/credentials/{credential_id}", response_model=AppCredentialOut)
async def admin_patch_credential_scope(
    credential_id: str,
    payload: ScopePatchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AppCredentialOut:
    from ai_api.auth import audit
    from ai_api.models import ActorType, AuditEventType

    service = AllocationService(session)
    cred = await service.get_credential(credential_id)
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "credential not found"}},
        )
    if payload.name is not None:
        await service.rename_credential(credential_id, payload.name)
        await audit.record(
            session, event_type=AuditEventType.credential_renamed,
            actor_type=ActorType.admin, target_type="credential", target_id=credential_id,
        )
    try:
        await service.patch_credential_scope(credential_id, payload.add, payload.remove)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "allocation not owned by the key's member"}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "invalid_scope", "message": str(exc)}},
        ) from exc
    if payload.add:
        await audit.record(
            session, event_type=AuditEventType.credential_scope_added,
            actor_type=ActorType.admin, target_type="credential", target_id=credential_id,
            details={"add": list(payload.add)},
        )
    if payload.remove:
        await audit.record(
            session, event_type=AuditEventType.credential_scope_removed,
            actor_type=ActorType.admin, target_type="credential", target_id=credential_id,
            details={"remove": list(payload.remove)},
        )
    full = await service.get_credential_with_scope(credential_id)
    assert full is not None
    return _app_cred_out(full)
