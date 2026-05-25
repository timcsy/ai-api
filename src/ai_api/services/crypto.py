"""Phase 5: symmetric encryption for ProviderCredential.

Fernet (AES-128-CBC + HMAC-SHA256) with a single active key sourced from
`Settings.provider_key_enc_key` (env / K8s Secret). Module-level lazy init;
first call to `get_fernet()` validates the key and caches the Fernet object.

Startup-time validation is invoked from `main.py` lifespan so that a missing
or malformed key surfaces as a pod-startup failure (CrashLoopBackOff with a
clear error) instead of failing later at runtime.
"""
from __future__ import annotations

from cryptography.fernet import Fernet

from ai_api.config import get_settings


class CryptoConfigError(RuntimeError):
    """Raised when PROVIDER_KEY_ENC_KEY is missing or invalid."""


_FERNET: Fernet | None = None


def get_fernet() -> Fernet:
    """Return process-wide Fernet instance; raise CryptoConfigError on bad config."""
    global _FERNET
    if _FERNET is not None:
        return _FERNET
    raw = get_settings().provider_key_enc_key
    if not raw:
        raise CryptoConfigError(
            "PROVIDER_KEY_ENC_KEY is not set. "
            "In production this MUST be provided via K8s Secret; "
            "for local dev set it in your .env."
        )
    try:
        _FERNET = Fernet(raw.encode() if isinstance(raw, str) else raw)
    except (ValueError, TypeError) as exc:
        raise CryptoConfigError(
            f"PROVIDER_KEY_ENC_KEY is malformed (expected 32-byte url-safe base64): {exc}"
        ) from exc
    return _FERNET


def encrypt_str(plain: str) -> bytes:
    return get_fernet().encrypt(plain.encode("utf-8"))


def decrypt_str(token: bytes) -> str:
    return get_fernet().decrypt(token).decode("utf-8")
