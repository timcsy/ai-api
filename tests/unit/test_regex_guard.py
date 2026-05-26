"""Phase 5.2 T006 / US1: ReDoS guard for email_localpart_regex patterns."""
from __future__ import annotations

import pytest

from ai_api.services.tag_rules import UnsafeRegexError, guard_regex


def test_valid_pattern_passes_and_is_anchored():
    # student-id style: optional 0-2 letters then >=6 digits
    out = guard_regex(r"[a-z]{0,2}\d{6,}")
    assert out == r"^(?:[a-z]{0,2}\d{6,})$"


def test_already_anchored_pattern_kept():
    out = guard_regex(r"^[a-z]+\d+$")
    assert out == r"^[a-z]+\d+$"


def test_nested_quantifier_plus_plus_rejected():
    with pytest.raises(UnsafeRegexError):
        guard_regex(r"(a+)+$")


def test_nested_quantifier_star_star_rejected():
    with pytest.raises(UnsafeRegexError):
        guard_regex(r"(.*)*")


def test_too_many_quantifiers_rejected():
    with pytest.raises(UnsafeRegexError):
        guard_regex("a+a+a+a+a+a+a+a+a+a+a+")  # 11 quantifiers


def test_uncompilable_pattern_rejected():
    with pytest.raises(UnsafeRegexError):
        guard_regex(r"[unterminated")
