"""AllocationService: create / revoke / list allocations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ulid import ULID

from ai_api.auth.audit import record as audit_record
from ai_api.models import (
    ActorType,
    Allocation,
    AllocationOrigin,
    AllocationStatus,
    AuditEventType,
    Credential,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.credentials import GeneratedToken, fingerprint_for, generate_token


class InvalidAllocationState(Exception):
    """Raised when a state transition (pause/resume) is attempted from an
    incompatible status. Carries the current status for a clear 409 message."""

    def __init__(self, current: AllocationStatus, action: str) -> None:
        self.current = current
        self.action = action
        super().__init__(f"allocation is {current.value}, cannot {action}")


@dataclass(frozen=True)
class AllocationCreated:
    allocation: Allocation
    token: GeneratedToken


class AllocationService:
    BOOTSTRAP_ADMIN = "bootstrap-admin"

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self,
        member_id: str | None = None,
        resource_model: str = "",
        note: str | None = None,
        created_by: str | None = None,
        subject: str | None = None,
        quota_tokens_per_month: int | None = None,
        origin: AllocationOrigin = AllocationOrigin.admin,
    ) -> AllocationCreated:
        if not resource_model:
            raise ValueError("resource_model is required")
        if member_id is None and subject is None:
            raise ValueError("either member_id or subject must be provided")
        member: Member
        if member_id is None:
            # Phase 1 back-compat: auto-create external Member for a subject string.
            assert subject is not None
            member = await self._ensure_external_member(subject)
        else:
            found = await self._s.get(Member, member_id)
            if found is None:
                raise ValueError(f"member {member_id} not found")
            member = found
        now = datetime.now(UTC)
        token = generate_token()
        allocation = Allocation(
            id=str(ULID()),
            member_id=member.id,
            subject_snapshot=member.email,
            resource_model=resource_model,
            status=AllocationStatus.active,
            created_at=now,
            revoked_at=None,
            created_by=created_by or self.BOOTSTRAP_ADMIN,
            note=note,
            quota_tokens_per_month=quota_tokens_per_month,
            origin=origin,
        )
        credential = Credential(
            allocation_id=allocation.id,
            token_fingerprint=token.fingerprint,
            token_prefix=token.prefix,
            created_at=now,
        )
        allocation.credential = credential
        self._s.add(allocation)
        await self._s.flush()
        return AllocationCreated(allocation=allocation, token=token)

    async def rotate_token(
        self, allocation_id: str
    ) -> tuple[Allocation, GeneratedToken] | None:
        """Issue a new token for an existing allocation. Old token immediately invalid."""
        stmt = (
            select(Allocation)
            .options(selectinload(Allocation.credential))
            .where(Allocation.id == allocation_id)
        )
        allocation = (await self._s.execute(stmt)).scalar_one_or_none()
        if allocation is None:
            return None
        if allocation.status != AllocationStatus.active:
            raise ValueError("only active allocations can rotate token")
        token = generate_token()
        cred = allocation.credential
        cred.token_fingerprint = token.fingerprint
        cred.token_prefix = token.prefix
        cred.created_at = datetime.now(UTC)
        await self._s.flush()
        return allocation, token

    async def revoke(self, allocation_id: str, *, revoked_by: str | None = None) -> Allocation | None:
        stmt = (
            select(Allocation)
            .options(selectinload(Allocation.credential))
            .where(Allocation.id == allocation_id)
        )
        allocation = (await self._s.execute(stmt)).scalar_one_or_none()
        if allocation is None:
            return None
        if allocation.status != AllocationStatus.revoked:
            allocation.status = AllocationStatus.revoked
            allocation.revoked_at = datetime.now(UTC)
            await self._s.flush()
            # Phase 6: revoking a self-service allocation locks the member from
            # re-claiming this model until an admin unlocks.
            if allocation.origin == AllocationOrigin.self_service:
                await self._lock_reclaim(allocation, revoked_by=revoked_by)
        return allocation

    async def pause(self, allocation_id: str, *, paused_by: str | None = None) -> Allocation | None:
        """Reversibly pause an active allocation. Status-only — token, quota and
        reclaim locks are untouched (the key difference from revoke). Returns
        None if not found; raises InvalidAllocationState if not active."""
        allocation = await self.get(allocation_id)
        if allocation is None:
            return None
        if allocation.status != AllocationStatus.active:
            raise InvalidAllocationState(allocation.status, "pause")
        allocation.status = AllocationStatus.paused
        await self._s.flush()
        await audit_record(
            self._s,
            event_type=AuditEventType.allocation_paused,
            actor_type=ActorType.admin,
            actor_id=paused_by,
            target_type="allocation",
            target_id=allocation.id,
        )
        return allocation

    async def resume(self, allocation_id: str, *, resumed_by: str | None = None) -> Allocation | None:
        """Resume a paused allocation back to active. The original token works
        again immediately. Returns None if not found; raises
        InvalidAllocationState if not paused."""
        allocation = await self.get(allocation_id)
        if allocation is None:
            return None
        if allocation.status != AllocationStatus.paused:
            raise InvalidAllocationState(allocation.status, "resume")
        allocation.status = AllocationStatus.active
        await self._s.flush()
        await audit_record(
            self._s,
            event_type=AuditEventType.allocation_resumed,
            actor_type=ActorType.admin,
            actor_id=resumed_by,
            target_type="allocation",
            target_id=allocation.id,
        )
        return allocation

    async def _lock_reclaim(self, allocation: Allocation, *, revoked_by: str | None) -> None:
        from ai_api.models import SelfServiceReclaimLock

        existing = await self._s.get(
            SelfServiceReclaimLock, (allocation.member_id, allocation.resource_model)
        )
        if existing is None:
            self._s.add(
                SelfServiceReclaimLock(
                    member_id=allocation.member_id,
                    model_slug=allocation.resource_model,
                    locked_at=datetime.now(UTC),
                    locked_by=revoked_by or "admin",
                )
            )
            await self._s.flush()
        await audit_record(
            self._s,
            event_type=AuditEventType.self_service_reclaim_locked,
            actor_type=ActorType.admin,
            actor_id=revoked_by,
            target_type="member",
            target_id=allocation.member_id,
            details={"model": allocation.resource_model, "allocation_id": allocation.id},
        )

    async def get(self, allocation_id: str) -> Allocation | None:
        stmt = (
            select(Allocation)
            .options(selectinload(Allocation.credential))
            .where(Allocation.id == allocation_id)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        member_id: str | None = None,
        status: AllocationStatus | None = None,
    ) -> list[Allocation]:
        stmt = (
            select(Allocation)
            .options(selectinload(Allocation.credential))
            .order_by(Allocation.created_at.desc())
        )
        if member_id is not None:
            stmt = stmt.where(Allocation.member_id == member_id)
        if status is not None:
            stmt = stmt.where(Allocation.status == status)
        result = await self._s.execute(stmt)
        return cast(list[Allocation], list(result.scalars().all()))

    async def _ensure_external_member(self, subject: str) -> Member:
        """Phase 1 back-compat: find-or-create an `external` Member for a subject string."""
        email_n = subject.lower()
        stmt = select(Member).where(Member.email == email_n)
        existing = (await self._s.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing
        member = Member(
            id=str(ULID()),
            email=email_n,
            provider=MemberProvider.external,
            external_id=subject,
            display_name=subject,
            status=MemberStatus.active,
            password_hash=None,
            created_at=datetime.now(UTC),
            disabled_at=None,
            created_by=self.BOOTSTRAP_ADMIN,
        )
        self._s.add(member)
        await self._s.flush()
        return member

    async def lookup_by_token(self, plaintext: str) -> Allocation | None:
        fp = fingerprint_for(plaintext)
        stmt = (
            select(Allocation)
            .join(Credential, Credential.allocation_id == Allocation.id)
            .where(Credential.token_fingerprint == fp)
            .options(selectinload(Allocation.credential))
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()
