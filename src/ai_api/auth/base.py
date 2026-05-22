"""AuthProvider abstract base class + AuthResult / AuthError."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuthResult:
    """Successful authentication outcome — provider has verified the credential."""

    provider: str
    external_id: str
    email: str
    display_name: str
    raw_claims: dict[str, Any] | None = None


class AuthError(Exception):
    """Authentication failed in a way the user is allowed to learn about.

    Use generic codes (`invalid_credentials`, `not_allowed`, `disabled`) — do
    NOT include enumeration-helpful details (e.g. "email not found").
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class AuthProvider(ABC):
    """Interface every authentication provider must implement."""

    name: str  # e.g. "google_oidc" or "local_password"

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Verify credentials and return the canonical identity.

        Raise AuthError on any failure. Do NOT raise generic exceptions
        for credential errors.
        """
