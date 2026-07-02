"""Login-identifier helpers (spec 055): local login accepts a username OR an email.

The identifier is stored in the existing `members.email` column (reused, so no
schema change). Rules:
- folded to lowercase + stripped → lookups are case-insensitive (matches the
  pre-existing email behaviour).
- an identifier containing '@' is treated as an email and validated with EmailStr.
- otherwise it is a username: no whitespace, non-empty, <= 320 chars, and (by
  definition) no '@' — keeping the username / email namespaces clean.
"""
from __future__ import annotations

from pydantic import EmailStr, TypeAdapter, ValidationError

MAX_LEN = 320
_email_adapter: TypeAdapter[str] = TypeAdapter(EmailStr)


class InvalidIdentifierError(ValueError):
    """Raised when an identifier fails validation (creation path)."""


def normalize_identifier(raw: str) -> str:
    """Canonical form used for storage + lookup. Lookup-only paths (login) use
    this alone — an unmatchable value simply won't be found (generic error)."""
    return raw.strip().lower()


def is_email(identifier: str) -> bool:
    return "@" in identifier


def validate_identifier(raw: str) -> str:
    """Normalize + validate for the creation path. Returns the normalized
    identifier or raises InvalidIdentifierError."""
    ident = normalize_identifier(raw)
    if not ident:
        raise InvalidIdentifierError("identifier must not be empty")
    if len(ident) > MAX_LEN:
        raise InvalidIdentifierError(f"identifier must be at most {MAX_LEN} characters")
    if any(c.isspace() for c in raw):
        raise InvalidIdentifierError("identifier must not contain whitespace")
    if is_email(ident):
        try:
            _email_adapter.validate_python(ident)
        except ValidationError as exc:
            raise InvalidIdentifierError("invalid email address") from exc
    return ident
