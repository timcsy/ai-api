"""Spec 055: login identifier normalize + validate (username OR email)."""
from __future__ import annotations

import pytest

from ai_api.auth.identifier import (
    InvalidIdentifierError,
    is_email,
    normalize_identifier,
    validate_identifier,
)


def test_normalize_folds_case_and_strips() -> None:
    assert normalize_identifier("  Alice  ") == "alice"
    assert normalize_identifier("USER@X.COM") == "user@x.com"


def test_is_email() -> None:
    assert is_email("a@b.com") is True
    assert is_email("alice") is False


@pytest.mark.parametrize("raw,expected", [
    ("alice", "alice"),
    ("Alice", "alice"),
    ("bob.smith_01", "bob.smith_01"),
    ("user@ccsh.tn.edu.tw", "user@ccsh.tn.edu.tw"),
])
def test_validate_accepts_usernames_and_emails(raw: str, expected: str) -> None:
    assert validate_identifier(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "has space",
    "tab\tuser",
    "x" * 321,
    "not an email@",       # has '@' but invalid email
    "@nolocal.com",
])
def test_validate_rejects(raw: str) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_identifier(raw)
