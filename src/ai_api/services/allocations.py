"""AllocationService: create / revoke / list allocations."""
from __future__ import annotations

from collections.abc import Sequence
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
    CredentialAllocation,
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
    DEFAULT_CREDENTIAL_NAME = "預設"

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
        self._s.add(allocation)
        await self._s.flush()
        # Phase 20: the allocation starts with one default application key whose
        # scope is just this allocation (the 1:N special case of M:N).
        credential = Credential(
            id=str(ULID()),
            member_id=member.id,
            name=self.DEFAULT_CREDENTIAL_NAME,
            token_fingerprint=token.fingerprint,
            token_prefix=token.prefix,
            created_at=now,
        )
        self._s.add(credential)
        await self._s.flush()
        self._s.add(
            CredentialAllocation(
                credential_id=credential.id,
                allocation_id=allocation.id,
                resource_model=allocation.resource_model,
            )
        )
        await self._s.flush()
        # Populate the M:N relationship so callers can serialise `.credentials`
        # without a lazy load in the sync response path.
        await self._s.refresh(allocation, attribute_names=["credentials"])
        return AllocationCreated(allocation=allocation, token=token)

    async def rotate_token(
        self, allocation_id: str
    ) -> tuple[Allocation, GeneratedToken] | None:
        """Issue a new token for this allocation. Back-compat (Phase 18): rotates
        the first active credential in place; the new per-device add/revoke is the
        proper multi-device interface."""
        stmt = (
            select(Allocation)
            .options(selectinload(Allocation.credentials))
            .where(Allocation.id == allocation_id)
        )
        allocation = (await self._s.execute(stmt)).scalar_one_or_none()
        if allocation is None:
            return None
        if allocation.status != AllocationStatus.active:
            raise ValueError("only active allocations can rotate token")
        token = generate_token()
        now = datetime.now(UTC)
        cred = next((c for c in allocation.credentials if c.revoked_at is None), None)
        if cred is None:
            # No active key scoped to this allocation — issue a fresh default one.
            cred = Credential(
                id=str(ULID()),
                member_id=allocation.member_id,
                name=self.DEFAULT_CREDENTIAL_NAME,
                token_fingerprint=token.fingerprint,
                token_prefix=token.prefix,
                created_at=now,
            )
            self._s.add(cred)
            await self._s.flush()
            self._s.add(
                CredentialAllocation(
                    credential_id=cred.id,
                    allocation_id=allocation.id,
                    resource_model=allocation.resource_model,
                )
            )
        else:
            cred.token_fingerprint = token.fingerprint
            cred.token_prefix = token.prefix
            cred.created_at = now
        await self._s.flush()
        return allocation, token

    async def revoke(self, allocation_id: str, *, revoked_by: str | None = None) -> Allocation | None:
        stmt = (
            select(Allocation)
            .options(selectinload(Allocation.credentials))
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
            .options(selectinload(Allocation.credentials))
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
            .options(selectinload(Allocation.credentials))
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

    # ---- Phase 20: token resolution (model-aware) ----

    async def lookup_credential_by_token(self, plaintext: str) -> Credential | None:
        """Resolve a token to its application key (credential). Revoked keys
        (`revoked_at` set) no longer resolve; fingerprint is unique → ≤1 match.
        Updates `last_used_at` throttled (>5 min). The caller then picks the
        allocation by request model via `resolve_scope_allocation`."""
        fp = fingerprint_for(plaintext)
        cred = (
            await self._s.execute(
                select(Credential).where(
                    Credential.token_fingerprint == fp,
                    Credential.revoked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cred is None:
            return None
        now = datetime.now(UTC)
        last = cred.last_used_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)  # SQLite reads naive
        if last is None or (now - last).total_seconds() > 300:
            cred.last_used_at = now
        return cred

    async def resolve_scope_allocation(
        self, credential: Credential, model: str
    ) -> Allocation | None:
        """The allocation in this key's scope whose `resource_model == model`, or
        None if the model is outside the key's scope. `UNIQUE(credential_id,
        resource_model)` guarantees ≤1 (no billing ambiguity)."""
        stmt = (
            select(Allocation)
            .join(CredentialAllocation, CredentialAllocation.allocation_id == Allocation.id)
            .where(
                CredentialAllocation.credential_id == credential.id,
                CredentialAllocation.resource_model == model,
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def first_scope_allocation(self, credential: Credential) -> Allocation | None:
        """A representative allocation in the key's scope (oldest). Used to
        attribute a model_mismatch reject when the model isn't in scope."""
        stmt = (
            select(Allocation)
            .join(CredentialAllocation, CredentialAllocation.allocation_id == Allocation.id)
            .where(CredentialAllocation.credential_id == credential.id)
            .order_by(Allocation.created_at)
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def lookup_by_token(self, plaintext: str) -> Allocation | None:
        """Back-compat / display: resolve a token to a representative allocation in
        its scope (the first one). Proxy uses the model-aware pair above instead."""
        cred = await self.lookup_credential_by_token(plaintext)
        if cred is None:
            return None
        stmt = (
            select(Allocation)
            .join(CredentialAllocation, CredentialAllocation.allocation_id == Allocation.id)
            .where(CredentialAllocation.credential_id == cred.id)
            .options(selectinload(Allocation.credentials))
            .order_by(Allocation.created_at)
        )
        return (await self._s.execute(stmt)).scalars().first()

    # ---- application keys (credentials) ----

    async def add_credential(
        self, allocation: Allocation, name: str
    ) -> tuple[Credential, GeneratedToken]:
        """Back-compat (Phase 18/19): issue a key scoped to a SINGLE allocation
        (owned by that allocation's member). The general multi-allocation path is
        `create_member_credential`."""
        return await self.create_member_credential(
            allocation.member_id, name, [allocation.id]
        )

    async def create_member_credential(
        self, member_id: str, name: str, allocation_ids: Sequence[str]
    ) -> tuple[Credential, GeneratedToken]:
        """Create a named application key for a member, scoped to a set of the
        member's own allocations. Verifies ownership and that the scope's models
        are distinct. Plaintext token returned once (show-once)."""
        if not allocation_ids:
            raise ValueError("a credential needs at least one allocation")
        allocs = await self._owned_allocations(member_id, allocation_ids)
        token = generate_token()
        now = datetime.now(UTC)
        credential = Credential(
            id=str(ULID()),
            member_id=member_id,
            name=name,
            token_fingerprint=token.fingerprint,
            token_prefix=token.prefix,
            created_at=now,
        )
        self._s.add(credential)
        await self._s.flush()
        for a in allocs:
            self._s.add(
                CredentialAllocation(
                    credential_id=credential.id,
                    allocation_id=a.id,
                    resource_model=a.resource_model,
                )
            )
        await self._s.flush()
        return credential, token

    async def _owned_allocations(
        self, member_id: str, allocation_ids: Sequence[str]
    ) -> Sequence[Allocation]:
        """Load the allocations, asserting they all belong to the member and have
        distinct resource_models (no billing ambiguity). Raises PermissionError /
        ValueError otherwise."""
        seen_ids: list[str] = list(dict.fromkeys(allocation_ids))  # dedupe, keep order
        allocs: list[Allocation] = []
        models: set[str] = set()
        for aid in seen_ids:
            a = await self._s.get(Allocation, aid)
            if a is None or a.member_id != member_id:
                raise PermissionError(f"allocation {aid} is not the member's")
            if a.resource_model in models:
                raise ValueError(f"duplicate model '{a.resource_model}' in scope")
            models.add(a.resource_model)
            allocs.append(a)
        return allocs

    async def patch_credential_scope(
        self, credential_id: str, add: Sequence[str], remove: Sequence[str]
    ) -> Credential | None:
        """Add/remove allocations from a key's scope. Verifies added allocations
        belong to the key's owner and that the resulting scope has distinct models
        and ≥1 allocation. Returns None if not found; raises PermissionError /
        ValueError."""
        cred = await self._s.get(Credential, credential_id)
        if cred is None:
            return None
        links = list(
            (
                await self._s.execute(
                    select(CredentialAllocation).where(
                        CredentialAllocation.credential_id == credential_id
                    )
                )
            ).scalars().all()
        )
        by_alloc = {ln.allocation_id: ln for ln in links}
        remove_set = set(remove)
        add_allocs = await self._owned_allocations(
            cred.member_id, [a for a in add if a not in by_alloc]
        )
        kept = [ln for ln in links if ln.allocation_id not in remove_set]
        kept_models = {ln.resource_model for ln in kept}
        for a in add_allocs:
            if a.resource_model in kept_models:
                raise ValueError(f"duplicate model '{a.resource_model}' in scope")
        if not kept and not add_allocs:
            raise ValueError("a credential needs at least one allocation")
        for ln in links:
            if ln.allocation_id in remove_set:
                await self._s.delete(ln)
        for a in add_allocs:
            self._s.add(
                CredentialAllocation(
                    credential_id=credential_id,
                    allocation_id=a.id,
                    resource_model=a.resource_model,
                )
            )
        await self._s.flush()
        return cred

    async def list_member_credentials(self, member_id: str) -> Sequence[Credential]:
        """All of a member's application keys (incl. revoked), with scope loaded."""
        stmt = (
            select(Credential)
            .where(Credential.member_id == member_id)
            .options(selectinload(Credential.allocations))
            .order_by(Credential.created_at.desc())
        )
        result = await self._s.execute(stmt)
        return cast(list[Credential], list(result.scalars().all()))

    async def list_credentials(self, allocation_id: str) -> Sequence[Credential]:
        """Back-compat (Phase 18): keys whose scope INCLUDES this allocation."""
        stmt = (
            select(Credential)
            .join(CredentialAllocation, CredentialAllocation.credential_id == Credential.id)
            .where(CredentialAllocation.allocation_id == allocation_id)
            .options(selectinload(Credential.allocations))
            .order_by(Credential.created_at.desc())
        )
        result = await self._s.execute(stmt)
        return cast(list[Credential], list(result.scalars().all()))

    async def get_credential(self, credential_id: str) -> Credential | None:
        return await self._s.get(Credential, credential_id)

    async def rename_credential(self, credential_id: str, name: str) -> Credential | None:
        """Rename a key (label only — does not touch token or scope)."""
        cred = await self._s.get(Credential, credential_id)
        if cred is None:
            return None
        cred.name = name
        await self._s.flush()
        return cred

    async def get_credential_with_scope(self, credential_id: str) -> Credential | None:
        """A credential with its scope (allocations) eager-loaded for serialisation."""
        return (
            await self._s.execute(
                select(Credential)
                .where(Credential.id == credential_id)
                .options(selectinload(Credential.allocations))
            )
        ).scalar_one_or_none()

    async def credential_in_allocation_scope(
        self, credential_id: str, allocation_id: str
    ) -> bool:
        """Whether a credential's scope includes the given allocation."""
        row = (
            await self._s.execute(
                select(CredentialAllocation.credential_id).where(
                    CredentialAllocation.credential_id == credential_id,
                    CredentialAllocation.allocation_id == allocation_id,
                )
            )
        ).first()
        return row is not None

    async def revoke_credential(self, credential_id: str) -> Credential | None:
        """Soft-revoke a single credential (`revoked_at = now`); idempotent. Other
        credentials of the same allocation keep working (no collateral revoke)."""
        credential = await self._s.get(Credential, credential_id)
        if credential is None:
            return None
        if credential.revoked_at is None:
            credential.revoked_at = datetime.now(UTC)
            await self._s.flush()
        return credential

    async def rotate_credential(
        self, credential_id: str
    ) -> tuple[Credential, GeneratedToken] | None:
        """Issue a fresh token for an existing credential in place — keeps the
        device name and creation date, the old token immediately invalid. The
        convenient alternative to revoke-then-add for one device. Returns None if
        not found; raises ValueError if the credential is already revoked."""
        credential = await self._s.get(Credential, credential_id)
        if credential is None:
            return None
        if credential.revoked_at is not None:
            raise ValueError("cannot rotate a revoked credential")
        token = generate_token()
        credential.token_fingerprint = token.fingerprint
        credential.token_prefix = token.prefix
        credential.last_used_at = None
        await self._s.flush()
        return credential, token
