"""LocalPasswordProvider: Argon2id hashing + verification + complexity policy."""
from __future__ import annotations

from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ai_api.auth.base import AuthError, AuthProvider, AuthResult

# Light blacklist; in production we'd load a longer list from disk.
COMMON_PASSWORDS = {
    "password123", "qwerty12345", "letmein2024", "12345678901",
    "admin12345", "iloveyou123", "welcome123!", "passw0rd!!",
}

MIN_LENGTH = 10

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    enforce_policy(plaintext)
    return _hasher.hash(plaintext)


def verify_password(stored_hash: str, plaintext: str) -> bool:
    try:
        return _hasher.verify(stored_hash, plaintext)
    except (VerifyMismatchError, InvalidHashError):
        return False


def enforce_policy(plaintext: str) -> None:
    if len(plaintext) < MIN_LENGTH:
        raise ValueError(f"password must be at least {MIN_LENGTH} characters")
    if plaintext.lower() in COMMON_PASSWORDS:
        raise ValueError("password is too common")


class LocalPasswordProvider(AuthProvider):
    name = "local_password"

    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        # Stub — the local login flow handles lookup + verification directly because
        # it needs DB access. This class exists for parity with AuthProvider interface.
        raise AuthError("not_implemented", "local provider uses dedicated login handler")
