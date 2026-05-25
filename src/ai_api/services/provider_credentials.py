"""Phase 5: ProviderCredential service.

US1 MVP scope: get_next_credential (round-robin by last_used_at) + decrypt.
Full admin CRUD lands in US2.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import ProviderCredential, ProviderCredentialStatus
from ai_api.services.crypto import decrypt_str, encrypt_str


class ProviderUnavailableError(Exception):
    """Raised when no active credential exists for the requested provider."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"no active credential for provider {provider!r}")
        self.provider = provider


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
        cred.last_used_at = datetime.now(UTC)
        await self._s.flush()
        plain = decrypt_str(cred.enc_key)
        return ResolvedCredential(
            id=cred.id,
            provider=cred.provider,
            label=cred.label,
            api_key=plain,
            base_url=cred.base_url,
            extra_config=cred.extra_config,
        )

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
        return cred
