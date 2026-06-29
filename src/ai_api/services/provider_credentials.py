"""Phase 5: ProviderCredential service — full admin CRUD + round-robin selection."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.auth.audit import record as audit_record
from ai_api.db import get_sessionmaker
from ai_api.models import ActorType, AuditEventType, ProviderCredential, ProviderCredentialStatus
from ai_api.services.crypto import decrypt_str, encrypt_str


class ProviderUnavailableError(Exception):
    """Raised when no active credential exists for the requested provider."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"no active credential for provider {provider!r}")
        self.provider = provider


class DuplicateLabelError(Exception):
    """Raised when (provider, label) already exists."""


class CannotRotateError(Exception):
    """Raised when a non-active credential is asked to rotate."""


class AlreadyDisabledError(Exception):
    """Raised when an already-disabled credential is asked to disable."""


@dataclass(frozen=True)
class ResolvedCredential:
    """Plaintext-bearing credential ready for upstream use; never persist this."""

    id: str
    provider: str
    label: str
    api_key: str
    base_url: str | None
    extra_config: dict[str, Any] | None


def _fingerprint(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()[:16]


class ProviderCredentialService:
    BOOTSTRAP_ADMIN = "bootstrap-admin"

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_next(self, provider: str) -> ResolvedCredential | None:
        """Pick the next active credential for `provider` via round-robin (last_used_at ASC NULLS FIRST)."""
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.provider == provider,
                ProviderCredential.status == ProviderCredentialStatus.active,
            )
            .order_by(
                ProviderCredential.last_used_at.asc().nulls_first(),
                ProviderCredential.created_at.asc(),
            )
            .limit(1)
        )
        cred = (await self._s.execute(stmt)).scalar_one_or_none()
        if cred is None:
            return None
        first_use = cred.last_used_at is None
        # Build the resolved credential from the row as read. We deliberately do
        # NOT mutate `cred` on the request session (that would re-emit the UPDATE
        # at request-commit time, re-taking the row lock across the upstream call).
        resolved = ResolvedCredential(
            id=cred.id,
            provider=cred.provider,
            label=cred.label,
            api_key=decrypt_str(cred.enc_key),
            base_url=cred.base_url,
            extra_config=cred.extra_config,
        )
        cred_id, cred_provider, cred_label = cred.id, cred.provider, cred.label

        # Update last_used_at (round-robin bookkeeping) in its OWN short-lived
        # transaction so the row lock is held for milliseconds, never across the
        # slow upstream call. With a shared provider key, holding this lock across
        # upstream serialized every concurrent request on one row → DB connection
        # pool exhaustion (QueuePool TimeoutError) under load.
        now = datetime.now(UTC)
        async with get_sessionmaker()() as s2:
            await s2.execute(
                update(ProviderCredential)
                .where(ProviderCredential.id == cred_id)
                .values(last_used_at=now)
            )
            if first_use:
                await audit_record(
                    s2,
                    event_type=AuditEventType.provider_credential_used_first_time,
                    actor_type=ActorType.system,
                    target_type="provider_credential",
                    target_id=cred_id,
                    details={"provider": cred_provider, "label": cred_label},
                )
            await s2.commit()
        return resolved

    async def create(
        self,
        *,
        provider: str,
        label: str,
        api_key: str,
        base_url: str | None = None,
        extra_config: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> ProviderCredential:
        """Create a new credential. Plaintext is encrypted; caller may keep `api_key` for
        one-time display before discarding."""
        # Pre-check (provider, label) uniqueness for a clean 409 instead of relying
        # on DB UNIQUE constraint error parsing.
        existing = await self._s.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider == provider,
                ProviderCredential.label == label,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateLabelError(
                f"credential with provider={provider!r} label={label!r} already exists"
            )
        cred = ProviderCredential(
            id=str(ULID()),
            provider=provider,
            label=label,
            enc_key=encrypt_str(api_key),
            fingerprint=_fingerprint(api_key),
            base_url=base_url,
            extra_config=extra_config,
            status=ProviderCredentialStatus.active,
            created_at=datetime.now(UTC),
            created_by=created_by or self.BOOTSTRAP_ADMIN,
        )
        self._s.add(cred)
        await self._s.flush()
        await audit_record(
            self._s,
            event_type=AuditEventType.provider_credential_created,
            actor_type=ActorType.admin,
            actor_id=created_by,
            target_type="provider_credential",
            target_id=cred.id,
            details={"provider": provider, "label": label, "fingerprint": cred.fingerprint},
        )
        return cred

    async def list(
        self,
        provider: str | None = None,
        status: ProviderCredentialStatus | None = None,
    ) -> list[ProviderCredential]:
        stmt = select(ProviderCredential).order_by(ProviderCredential.created_at.desc())
        if provider is not None:
            stmt = stmt.where(ProviderCredential.provider == provider)
        if status is not None:
            stmt = stmt.where(ProviderCredential.status == status)
        return list((await self._s.execute(stmt)).scalars().all())

    async def get(self, credential_id: str) -> ProviderCredential | None:
        return await self._s.get(ProviderCredential, credential_id)

    async def rotate(self, credential_id: str, new_api_key: str) -> ProviderCredential | None:
        """Replace enc_key + fingerprint in place; old plaintext immediately invalid."""
        cred = await self._s.get(ProviderCredential, credential_id)
        if cred is None:
            return None
        if cred.status != ProviderCredentialStatus.active:
            raise CannotRotateError(
                f"credential {credential_id} is not active (status={cred.status.value})"
            )
        cred.enc_key = encrypt_str(new_api_key)
        cred.fingerprint = _fingerprint(new_api_key)
        await self._s.flush()
        await audit_record(
            self._s,
            event_type=AuditEventType.provider_credential_rotated,
            actor_type=ActorType.admin,
            target_type="provider_credential",
            target_id=cred.id,
            details={"provider": cred.provider, "label": cred.label, "fingerprint": cred.fingerprint},
        )
        return cred

    async def disable(self, credential_id: str) -> ProviderCredential | None:
        cred = await self._s.get(ProviderCredential, credential_id)
        if cred is None:
            return None
        if cred.status == ProviderCredentialStatus.disabled:
            raise AlreadyDisabledError(f"credential {credential_id} is already disabled")
        cred.status = ProviderCredentialStatus.disabled
        cred.disabled_at = datetime.now(UTC)
        await self._s.flush()
        await audit_record(
            self._s,
            event_type=AuditEventType.provider_credential_disabled,
            actor_type=ActorType.admin,
            target_type="provider_credential",
            target_id=cred.id,
            details={"provider": cred.provider, "label": cred.label},
        )
        return cred
