"""Phase 13: NotificationConfigService — singleton CRUD for SMTP config + recipients.

Encryption: SMTP password is Fernet-encrypted with the same key as ProviderCredential
(PROVIDER_KEY_ENC_KEY), via services/crypto.py. Decryption failures surface as
`NotificationConfigStatus.credentials_invalid` rather than an exception so the
admin UI can prompt for re-entry.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from cryptography.fernet import InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import NotificationConfig, NotificationConfigStatus
from ai_api.services.crypto import encrypt_str

# Conservative email regex; matches FastAPI/email-validator simple form.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class NotificationConfigValidationError(ValueError):
    """Raised when input config is malformed (host empty / port range / bad email)."""


def _validate_email(addr: str, *, field: str) -> None:
    if not isinstance(addr, str) or not _EMAIL_RE.match(addr):
        raise NotificationConfigValidationError(f"{field}: invalid email format ({addr!r})")


def _password_fingerprint(ciphertext: bytes) -> str:
    """`abcd…wxyz` — first 4 + last 4 bytes of ciphertext as hex (UI-safe mask)."""
    if not ciphertext or len(ciphertext) < 8:
        return "***"
    return ciphertext[:4].hex() + "..." + ciphertext[-4:].hex()


class NotificationConfigService:
    BOOTSTRAP_ADMIN = "bootstrap-admin"

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self) -> NotificationConfig | None:
        return (
            await self._s.execute(select(NotificationConfig).limit(1))
        ).scalar_one_or_none()

    async def save(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        sender_email: str,
        sender_name: str,
        recipients: list[str],
        enabled: bool = True,
        created_by: str | None = None,
    ) -> NotificationConfig:
        # Validate
        if not isinstance(smtp_host, str) or not smtp_host.strip():
            raise NotificationConfigValidationError("smtp_host: must be non-empty")
        if not isinstance(smtp_port, int) or not (1 <= smtp_port <= 65535):
            raise NotificationConfigValidationError(
                "smtp_port: must be integer between 1 and 65535"
            )
        if not isinstance(smtp_username, str) or not smtp_username.strip():
            raise NotificationConfigValidationError("smtp_username: must be non-empty")
        if not isinstance(smtp_password, str) or not smtp_password:
            raise NotificationConfigValidationError("smtp_password: must be non-empty")
        _validate_email(sender_email, field="sender_email")
        if not isinstance(recipients, list) or not all(isinstance(r, str) for r in recipients):
            raise NotificationConfigValidationError("recipients: must be a list of email strings")
        for r in recipients:
            _validate_email(r, field="recipients")

        encrypted = encrypt_str(smtp_password)
        now = datetime.now(UTC)

        existing = await self.get()
        if existing is None:
            cfg = NotificationConfig(
                id=1,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_username=smtp_username,
                smtp_password_encrypted=encrypted,
                sender_email=sender_email,
                sender_name=sender_name or "AI API Manager",
                recipients=recipients,
                enabled=enabled,
                status=NotificationConfigStatus.pending_test,
                created_at=now,
                updated_at=now,
                created_by=created_by or self.BOOTSTRAP_ADMIN,
            )
            self._s.add(cfg)
        else:
            cfg = existing
            cfg.smtp_host = smtp_host
            cfg.smtp_port = smtp_port
            cfg.smtp_username = smtp_username
            cfg.smtp_password_encrypted = encrypted
            cfg.sender_email = sender_email
            cfg.sender_name = sender_name or "AI API Manager"
            cfg.recipients = recipients
            cfg.enabled = enabled
            # Reset status on any save — admin should re-test after changes
            cfg.status = NotificationConfigStatus.pending_test
            cfg.last_test_at = None
            cfg.last_test_outcome = None
            cfg.last_test_error = None
            cfg.updated_at = now
        await self._s.flush()
        return cfg

    async def delete(self) -> bool:
        result = await self._s.execute(delete(NotificationConfig))
        await self._s.flush()
        return result.rowcount > 0

    @staticmethod
    def to_response(cfg: NotificationConfig) -> dict[str, object]:
        """Serialise a NotificationConfig for admin UI (password masked)."""
        return {
            "smtp_host": cfg.smtp_host,
            "smtp_port": cfg.smtp_port,
            "smtp_username": cfg.smtp_username,
            "smtp_password_fingerprint": _password_fingerprint(cfg.smtp_password_encrypted),
            "sender_email": cfg.sender_email,
            "sender_name": cfg.sender_name,
            "recipients": cfg.recipients,
            "enabled": cfg.enabled,
            "status": cfg.status.value if isinstance(
                cfg.status, NotificationConfigStatus
            ) else cfg.status,
            "last_test_at": cfg.last_test_at.isoformat() if cfg.last_test_at else None,
            "last_test_outcome": cfg.last_test_outcome,
            "last_test_error": cfg.last_test_error,
            "created_at": cfg.created_at.isoformat(),
            "updated_at": cfg.updated_at.isoformat(),
            "created_by": cfg.created_by,
        }


__all__ = [
    "InvalidToken",  # re-export for callers that want to detect decrypt failures
    "NotificationConfigService",
    "NotificationConfigValidationError",
]
