"""AllocationService: create / revoke / list allocations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ulid import ULID

from ai_api.models import (
    Allocation,
    AllocationStatus,
    Credential,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.credentials import GeneratedToken, fingerprint_for, generate_token


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

    async def revoke(self, allocation_id: str) -> Allocation | None:
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
        return allocation

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
