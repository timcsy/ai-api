"""Login-identifier helpers (spec 055): local login accepts a username OR an email.

The identifier is stored in the existing `members.email` column (reused, so no
schema change). It is a **free-form login name** — '@' is allowed and the value is
NOT required to be a valid email (nothing is ever mailed to a member; the string is
just an unverified login identifier). Only structural rules apply:
- folded to lowercase + stripped → lookups are case-insensitive (matches the
  pre-existing email behaviour).
- non-empty, no whitespace, <= 320 chars.
"""
from __future__ import annotations

MAX_LEN = 320


class InvalidIdentifierError(ValueError):
    """Raised when an identifier fails validation (creation path)."""


def normalize_identifier(raw: str) -> str:
    """Canonical form used for storage + lookup. Lookup-only paths (login) use
    this alone — an unmatchable value simply won't be found (generic error)."""
    return raw.strip().lower()


def is_email(identifier: str) -> bool:
    """Best-effort hint (an identifier that looks like an email). Not a gate —
    '@' is allowed in usernames; this is only used where email-shaped handling
    is a convenience (e.g. UI)."""
    return "@" in identifier


def validate_identifier(raw: str) -> str:
    """Normalize + validate for the creation path. Returns the normalized
    identifier or raises InvalidIdentifierError. '@' is allowed (not validated as
    an email); only structural rules are enforced."""
    ident = normalize_identifier(raw)
    if not ident:
        raise InvalidIdentifierError("identifier must not be empty")
    if len(ident) > MAX_LEN:
        raise InvalidIdentifierError(f"identifier must be at most {MAX_LEN} characters")
    if any(c.isspace() for c in raw):
        raise InvalidIdentifierError("identifier must not contain whitespace")
    return ident
