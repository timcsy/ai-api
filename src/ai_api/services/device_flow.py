"""DeviceFlowService — Phase 19: RFC 8628-style device authorization for Codex.

The install script calls `authorize()` to get a device_code + user_code, the
member approves in the browser (`approve()`, picking an allocation), which mints
a per-device Credential (Phase 18) and stashes its plaintext Fernet-encrypted on
the row; the script's next `poll()` delivers that plaintext exactly once.
"""
from __future__ import annotations

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.auth.audit import record as audit_record
from ai_api.models import (
    ActorType,
    Allocation,
    AuditEventType,
    CredentialAllocation,
    DeviceAuthorization,
    DeviceAuthStatus,
    Member,
)
from ai_api.services.allocations import AllocationService
from ai_api.services.crypto import decrypt_str, encrypt_str

# user_code alphabet — Crockford-ish, no ambiguous chars (0/O, 1/I/L).
_USER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


@dataclass(frozen=True)
class AuthorizeResult:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


@dataclass(frozen=True)
class PollResult:
    """status ∈ {authorization_pending, slow_down, expired_token, access_denied,
    success, not_found}. token/token_prefix/credential_id/model only set on
    success. ``model`` is the representative scoped model (resource_model of the
    first chosen allocation) so the install script can pin Codex's default model
    instead of falling back to Codex's built-in default."""

    status: str
    token: str | None = None
    token_prefix: str | None = None
    credential_id: str | None = None
    model: str | None = None


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes for DateTime(timezone=True).
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class DeviceAuthError(Exception):
    """Raised when a device authorization cannot be approved/denied (not found,
    expired, or already terminal)."""


class DeviceFlowService:
    EXPIRES_IN = 600  # seconds
    INTERVAL = 5  # seconds
    VERIFICATION_PATH = "/device"

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @staticmethod
    def _gen_user_code() -> str:
        raw = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(8))
        return f"{raw[:4]}-{raw[4:]}"

    async def authorize(self, device_label: str | None = None) -> AuthorizeResult:
        now = datetime.now(UTC)
        device_code = secrets.token_urlsafe(32)
        # Retry user_code on the (rare) unique collision.
        user_code = self._gen_user_code()
        for _ in range(5):
            exists = (
                await self._s.execute(
                    select(DeviceAuthorization.id).where(
                        DeviceAuthorization.user_code == user_code
                    )
                )
            ).first()
            if exists is None:
                break
            user_code = self._gen_user_code()
        row = DeviceAuthorization(
            id=str(ULID()),
            device_code=device_code,
            user_code=user_code,
            status=DeviceAuthStatus.pending,
            device_label=(device_label or None),
            created_at=now,
            expires_at=now + timedelta(seconds=self.EXPIRES_IN),
            poll_interval=self.INTERVAL,
        )
        self._s.add(row)
        await self._s.flush()
        return AuthorizeResult(
            device_code=device_code,
            user_code=user_code,
            verification_uri=self.VERIFICATION_PATH,
            verification_uri_complete=f"{self.VERIFICATION_PATH}?code={user_code}",
            expires_in=self.EXPIRES_IN,
            interval=self.INTERVAL,
        )

    async def _by_user_code(self, user_code: str) -> DeviceAuthorization | None:
        return (
            await self._s.execute(
                select(DeviceAuthorization).where(DeviceAuthorization.user_code == user_code)
            )
        ).scalar_one_or_none()

    async def get_pending(self, user_code: str) -> DeviceAuthorization | None:
        """Return the request if it is still actionable (pending + not expired)."""
        row = await self._by_user_code(user_code)
        if row is None:
            return None
        if row.status != DeviceAuthStatus.pending:
            return None
        if datetime.now(UTC) >= _aware(row.expires_at):
            row.status = DeviceAuthStatus.expired
            await self._s.flush()
            return None
        return row

    async def approve(
        self, user_code: str, member: Member, allocation_ids: Sequence[str]
    ) -> DeviceAuthorization:
        """Approve a pending request, minting one application key scoped to the
        chosen allocations (Phase 20: a Codex install can cover several models).
        Raises DeviceAuthError if not actionable, PermissionError if any allocation
        isn't the member's, ValueError on duplicate models."""
        row = await self.get_pending(user_code)
        if row is None:
            raise DeviceAuthError("device authorization not found, expired, or already used")
        if not allocation_ids:
            raise ValueError("at least one allocation is required")
        credential, token = await AllocationService(self._s).create_member_credential(
            member.id, row.device_label or "Codex", allocation_ids
        )
        now = datetime.now(UTC)
        row.member_id = member.id
        row.allocation_id = allocation_ids[0]  # representative (back-compat column)
        row.credential_id = credential.id
        row.encrypted_token = encrypt_str(token.plaintext).decode("ascii")
        row.status = DeviceAuthStatus.approved
        row.approved_at = now
        await audit_record(
            self._s,
            event_type=AuditEventType.device_authorization_approved,
            actor_type=ActorType.member,
            actor_id=member.id,
            target_type="device_authorization",
            target_id=row.id,
            details={"allocation_ids": list(allocation_ids), "credential_id": credential.id},
        )
        await self._s.flush()
        return row

    async def deny(self, user_code: str, member: Member) -> bool:
        row = await self.get_pending(user_code)
        if row is None:
            return False
        row.status = DeviceAuthStatus.denied
        await audit_record(
            self._s,
            event_type=AuditEventType.device_authorization_denied,
            actor_type=ActorType.member,
            actor_id=member.id,
            target_type="device_authorization",
            target_id=row.id,
        )
        await self._s.flush()
        return True

    async def poll(self, device_code: str) -> PollResult:
        row = (
            await self._s.execute(
                select(DeviceAuthorization).where(
                    DeviceAuthorization.device_code == device_code
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return PollResult("not_found")
        now = datetime.now(UTC)

        if row.status == DeviceAuthStatus.pending:
            if now >= _aware(row.expires_at):
                row.status = DeviceAuthStatus.expired
                await self._s.flush()
                return PollResult("expired_token")
            last = row.last_polled_at
            row.last_polled_at = now
            await self._s.flush()
            if last is not None and (now - _aware(last)).total_seconds() < row.poll_interval:
                return PollResult("slow_down")
            return PollResult("authorization_pending")

        if row.status == DeviceAuthStatus.denied:
            return PollResult("access_denied")

        if row.status == DeviceAuthStatus.expired:
            return PollResult("expired_token")

        # approved
        if row.encrypted_token is None:
            # Already delivered once → nothing more to hand out.
            return PollResult("expired_token")
        plaintext = decrypt_str(row.encrypted_token.encode("ascii"))
        row.encrypted_token = None  # single-use delivery
        # Model to pin in Codex's config. Prefer the **bare** slug (strip the
        # provider prefix) so it matches Codex's built-in catalog entry and is
        # selectable in /model — but only when unambiguous within this key's
        # scope; otherwise pin the full prefixed slug to avoid a broken default.
        model: str | None = None
        if row.allocation_id is not None:
            repr_model = (
                await self._s.execute(
                    select(Allocation.resource_model).where(Allocation.id == row.allocation_id)
                )
            ).scalar_one_or_none()
            if repr_model is not None:
                bare = repr_model.split("/", 1)[-1]
                scope = (
                    await self._s.execute(
                        select(CredentialAllocation.resource_model).where(
                            CredentialAllocation.credential_id == row.credential_id
                        )
                    )
                ).scalars().all()
                same_bare = [m for m in scope if m.split("/", 1)[-1] == bare]
                model = bare if len(same_bare) == 1 else repr_model
        await self._s.flush()
        return PollResult(
            "success",
            token=plaintext,
            token_prefix=plaintext[:8],
            credential_id=row.credential_id,
            model=model,
        )
