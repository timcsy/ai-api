"""Phase 30 (039) US1: safe-delete a member that still owns allocations.

Verifies the service-level explicit cascade (research R1: don't rely on DB
ondelete — SQLite test env has no FK pragma): allocations / credentials /
credential_allocations are removed, the member is gone, BUT the member's
CallRecord rows are PRESERVED with allocation_id set to NULL (orphan-retain,
subject kept) so usage history survives for audit.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import (
    Allocation,
    AuditEventType,
    AuthAuditLog,
    CallOutcome,
    CallRecord,
    Credential,
    CredentialAllocation,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.allocations import AllocationService
from ai_api.services.members import MemberService


async def _seed_member(s, email: str, *, is_admin: bool = False) -> str:
    m = Member(
        id=str(ULID()), email=email.lower(), provider=MemberProvider.external,
        external_id=email, display_name=email, status=MemberStatus.active,
        password_hash=None, created_at=datetime.now(UTC), disabled_at=None,
        created_by="test", is_admin=is_admin,
    )
    s.add(m)
    await s.flush()
    return m.id


@pytest.mark.asyncio
async def test_safe_delete_member_with_allocation_preserves_callrecords(app_client: AsyncClient) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        member_id = await _seed_member(s, "alice@x.com")
        alloc = await AllocationService(s).create(
            member_id=member_id, resource_model="azure/gpt-4o-mini"
        )
        alloc_id = alloc.allocation.id
        cred, _tok = await AllocationService(s).create_member_credential(
            member_id, "k", [alloc_id]
        )
        # seed a couple of call records on the allocation
        for i in range(3):
            s.add(CallRecord(
                id=str(ULID()), request_id=f"r-{i}", allocation_id=alloc_id,
                subject="alice@x.com", model="azure/gpt-4o-mini",
                started_at=datetime.now(UTC), finished_at=datetime.now(UTC),
                status_code=200, outcome=CallOutcome.success,
                prompt_tokens=10, completion_tokens=5, total_tokens=15,
            ))
        await s.commit()

    async with sm() as s:
        ok = await MemberService(s).delete(member_id, acting_admin_id=None)
        await s.commit()
    assert ok is True

    async with sm() as s:
        # member + allocation + credential + link all gone
        assert (await s.get(Member, member_id)) is None
        assert (await s.execute(
            select(Allocation).where(Allocation.member_id == member_id)
        )).scalar_one_or_none() is None
        assert (await s.execute(
            select(Credential).where(Credential.member_id == member_id)
        )).scalar_one_or_none() is None
        assert (await s.execute(
            select(CredentialAllocation).where(CredentialAllocation.credential_id == cred.id)
        )).scalar_one_or_none() is None
        # CallRecords PRESERVED as orphans: still 3 rows, allocation_id NULL, subject kept
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.subject == "alice@x.com")
        )).scalars().all()
        assert len(rows) == 3
        assert all(r.allocation_id is None for r in rows)
        # audit recorded
        evt = (await s.execute(
            select(AuthAuditLog).where(
                AuthAuditLog.event_type == AuditEventType.member_deleted,
                AuthAuditLog.target_id == member_id,
            )
        )).scalar_one_or_none()
        assert evt is not None


@pytest.mark.asyncio
async def test_safe_delete_member_without_allocations(app_client: AsyncClient) -> None:
    """Regression: a member with no allocations still deletes cleanly."""
    sm = get_sessionmaker()
    async with sm() as s:
        member_id = await _seed_member(s, "bob@x.com")
        await s.commit()
    async with sm() as s:
        ok = await MemberService(s).delete(member_id, acting_admin_id=None)
        await s.commit()
    assert ok is True
    async with sm() as s:
        assert (await s.get(Member, member_id)) is None


@pytest.mark.asyncio
async def test_safe_delete_self_is_blocked(app_client: AsyncClient) -> None:
    from ai_api.services.members import CannotDeleteSelfError

    sm = get_sessionmaker()
    async with sm() as s:
        member_id = await _seed_member(s, "self@x.com", is_admin=True)
        await s.commit()
    async with sm() as s:
        with pytest.raises(CannotDeleteSelfError):
            await MemberService(s).delete(member_id, acting_admin_id=member_id)


@pytest.mark.asyncio
async def test_safe_delete_last_admin_is_blocked(app_client: AsyncClient) -> None:
    from ai_api.services.members import LastAdminCannotDeleteError

    sm = get_sessionmaker()
    async with sm() as s:
        only_admin = await _seed_member(s, "admin@x.com", is_admin=True)
        await s.commit()
    async with sm() as s:
        with pytest.raises(LastAdminCannotDeleteError):
            await MemberService(s).delete(only_admin, acting_admin_id=None)
