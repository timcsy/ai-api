"""Member service: create, list, get, update, delete + session linkage."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.auth import invitations, local, sessions
from ai_api.models import (
    Allocation,
    AllocationStatus,
    Member,
    MemberProvider,
    MemberStatus,
)


@dataclass(frozen=True)
class CreatedMember:
    member: Member
    invitation_plaintext: str | None = None


class MemberAlreadyExists(Exception):
    pass


class LastAdminCannotDemoteError(Exception):
    """Raised when demoting the only remaining active admin."""


class MemberHasActiveAllocations(Exception):
    pass


class MemberService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        email: str,
        provider: MemberProvider,
        display_name: str | None = None,
        external_id: str | None = None,
        initial_password: str | None = None,
        send_invitation: bool = True,
        created_by: str = "bootstrap-admin",
    ) -> CreatedMember:
        email_n = email.strip().lower()
        existing = (
            await self._db.execute(select(Member).where(Member.email == email_n))
        ).scalar_one_or_none()
        if existing is not None:
            raise MemberAlreadyExists(email_n)

        member = Member(
            id=str(ULID()),
            email=email_n,
            provider=provider,
            external_id=external_id,
            display_name=display_name or email_n,
            status=MemberStatus.active,
            password_hash=None,
            created_at=datetime.now(UTC),
            disabled_at=None,
            created_by=created_by,
        )
        invitation_plaintext: str | None = None
        if provider == MemberProvider.local_password:
            if initial_password:
                local.enforce_policy(initial_password)
                member.password_hash = local.hash_password(initial_password)
            elif send_invitation:
                pass  # invitation issued after flush below
            else:
                raise ValueError(
                    "local_password member needs initial_password or send_invitation=True"
                )

        self._db.add(member)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            raise MemberAlreadyExists(email_n) from exc

        if (
            provider == MemberProvider.local_password
            and initial_password is None
            and send_invitation
        ):
            issued = await invitations.issue(self._db, member.id, created_by=created_by)
            invitation_plaintext = issued.plaintext

        return CreatedMember(member=member, invitation_plaintext=invitation_plaintext)

    async def get(self, member_id: str) -> Member | None:
        return (
            await self._db.execute(select(Member).where(Member.id == member_id))
        ).scalar_one_or_none()

    async def get_by_email(self, email: str) -> Member | None:
        return (
            await self._db.execute(
                select(Member).where(Member.email == email.strip().lower())
            )
        ).scalar_one_or_none()

    async def list(
        self,
        *,
        provider: MemberProvider | None = None,
        status: MemberStatus | None = None,
        q: str | None = None,
    ) -> list[Member]:
        stmt = select(Member).order_by(Member.created_at.desc())
        if provider is not None:
            stmt = stmt.where(Member.provider == provider)
        if status is not None:
            stmt = stmt.where(Member.status == status)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(or_(Member.email.like(like), Member.display_name.like(like)))
        return list((await self._db.execute(stmt)).scalars().all())

    async def update(
        self,
        member_id: str,
        *,
        display_name: str | None = None,
        status: MemberStatus | None = None,
    ) -> Member | None:
        member = await self.get(member_id)
        if member is None:
            return None
        if display_name is not None:
            member.display_name = display_name
        if status is not None and status != member.status:
            member.status = status
            if status == MemberStatus.disabled:
                member.disabled_at = datetime.now(UTC)
                # Cascade-revoke active sessions for SC-006
                await sessions.revoke_all_for_member(
                    self._db, member.id, reason="member_disabled"
                )
        await self._db.flush()
        return member

    async def set_is_admin(
        self,
        member_id: str,
        is_admin: bool,
        actor: str = "admin",
    ) -> Member | None:
        """Promote/demote a member to/from admin role.

        Refuses to demote the last remaining active admin (raises
        :class:`LastAdminCannotDemoteError`).
        """
        from sqlalchemy import func as sa_func

        from ai_api.auth import audit
        from ai_api.models import ActorType, AuditEventType

        member = await self.get(member_id)
        if member is None:
            return None
        if member.is_admin == is_admin:
            return member  # no-op
        if not is_admin and member.is_admin:
            # Count other active admins
            count = await self._db.scalar(
                select(sa_func.count()).select_from(Member).where(
                    Member.is_admin.is_(True),
                    Member.status == MemberStatus.active,
                )
            )
            if (count or 0) <= 1:
                raise LastAdminCannotDemoteError(member_id)
        member.is_admin = is_admin
        await self._db.flush()
        event = (
            AuditEventType.member_promoted if is_admin else AuditEventType.member_demoted
        )
        await audit.record(
            self._db,
            event_type=event,
            actor_type=ActorType.admin,
            actor_id=actor,
            target_type="member",
            target_id=member.id,
        )
        return member

    async def delete(self, member_id: str) -> bool:
        member = await self.get(member_id)
        if member is None:
            return False
        # Refuse if any active allocations exist (FK is RESTRICT).
        active_alloc = (
            await self._db.execute(
                select(Allocation).where(
                    Allocation.member_id == member.id,
                    Allocation.status == AllocationStatus.active,
                )
            )
        ).scalar_one_or_none()
        if active_alloc is not None:
            raise MemberHasActiveAllocations(member_id)
        # Revoked allocations would also block FK; require admin to handle explicitly.
        any_alloc = (
            await self._db.execute(
                select(Allocation).where(Allocation.member_id == member.id)
            )
        ).scalar_one_or_none()
        if any_alloc is not None:
            raise MemberHasActiveAllocations(member_id)
        await self._db.delete(member)
        await self._db.flush()
        return True
