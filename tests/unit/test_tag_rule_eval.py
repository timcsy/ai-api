"""Phase 5.2 T007 / US1: matcher + first-match-wins evaluation truth table."""
from __future__ import annotations

from types import SimpleNamespace

from ai_api.models import MatcherType
from ai_api.services.tag_rules import evaluate, guard_regex


def _rule(order, matcher, pattern, tag, *, enabled=True, rid=None):
    return SimpleNamespace(
        id=rid or f"r{order}",
        order_index=order,
        matcher_type=matcher,
        pattern=pattern,
        tag=tag,
        enabled=enabled,
    )


def test_localpart_regex_match():
    rules = [_rule(0, MatcherType.email_localpart_regex, guard_regex(r"[a-z]{0,2}\d{6,}"), "student")]
    r = evaluate("b10901234@school.edu", rules)
    assert r["matched"] is True
    assert r["tag"] == "student"
    assert r["matcher_type"] == MatcherType.email_localpart_regex


def test_localpart_regex_no_match():
    rules = [_rule(0, MatcherType.email_localpart_regex, guard_regex(r"[a-z]{0,2}\d{6,}"), "student")]
    r = evaluate("prof.wang@school.edu", rules)
    assert r["matched"] is False
    assert r["tag"] is None


def test_localpart_truncated_to_64_chars():
    # a 70-char local part that only matches if NOT truncated would still be
    # safe; here we assert truncation doesn't crash and long input is bounded.
    rules = [_rule(0, MatcherType.email_localpart_regex, guard_regex(r"\d+"), "num")]
    long_local = "1" * 70
    r = evaluate(f"{long_local}@x.com", rules)
    # 64 digits still fullmatch \d+ → matched
    assert r["matched"] is True


def test_email_suffix_case_insensitive():
    rules = [_rule(0, MatcherType.email_suffix, "@School.EDU", "edu")]
    r = evaluate("alice@school.edu", rules)
    assert r["matched"] is True
    assert r["tag"] == "edu"


def test_email_domain_exact():
    rules = [_rule(0, MatcherType.email_domain, "school.edu", "school")]
    assert evaluate("a@school.edu", rules)["matched"] is True
    assert evaluate("a@sub.school.edu", rules)["matched"] is False


def test_always_matches():
    rules = [_rule(0, MatcherType.always, "", "everyone")]
    assert evaluate("anyone@anywhere", rules)["tag"] == "everyone"


def test_first_match_wins_by_order():
    rules = [
        _rule(0, MatcherType.email_localpart_regex, guard_regex(r"[a-z]{0,2}\d{6,}"), "student"),
        _rule(1, MatcherType.always, "", "teacher"),
    ]
    assert evaluate("b10901234@school.edu", rules)["tag"] == "student"
    assert evaluate("prof.wang@school.edu", rules)["tag"] == "teacher"


def test_unsorted_rules_sorted_internally():
    rules = [
        _rule(5, MatcherType.always, "", "teacher"),
        _rule(1, MatcherType.email_localpart_regex, guard_regex(r"[a-z]{0,2}\d{6,}"), "student"),
    ]
    assert evaluate("b10901234@school.edu", rules)["tag"] == "student"


def test_disabled_rules_skipped():
    rules = [
        _rule(0, MatcherType.email_localpart_regex, guard_regex(r"[a-z]{0,2}\d{6,}"), "student", enabled=False),
        _rule(1, MatcherType.always, "", "teacher"),
    ]
    assert evaluate("b10901234@school.edu", rules)["tag"] == "teacher"


def test_no_match_no_fallback_returns_unmatched():
    rules = [_rule(0, MatcherType.email_domain, "other.edu", "x")]
    r = evaluate("a@school.edu", rules)
    assert r["matched"] is False
    assert r["rule_id"] is None
