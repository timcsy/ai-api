"""Credential service: generate plaintext tokens + derive fingerprints."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

TOKEN_PREFIX = "aiapi_"


@dataclass(frozen=True)
class GeneratedToken:
    plaintext: str
    fingerprint: str
    prefix: str


def generate_token() -> GeneratedToken:
    """Generate a new credential token.

    Format: ``aiapi_<32-byte url-safe base64 random>``.
    Returns plaintext (returned to caller once), fingerprint (SHA-256 hex), and
    the first 8 chars of the plaintext for display.
    """
    random_part = secrets.token_urlsafe(32)
    plaintext = TOKEN_PREFIX + random_part
    fingerprint = fingerprint_for(plaintext)
    prefix = plaintext[:8]
    return GeneratedToken(plaintext=plaintext, fingerprint=fingerprint, prefix=prefix)


def fingerprint_for(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
