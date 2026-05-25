"""Phase 5.1 T003: evaluate_visibility pure-function truth table."""
from __future__ import annotations

from types import SimpleNamespace

from ai_api.models import DefaultAccess
from ai_api.services.model_access import evaluate_visibility


def _model(provider: str, default: DefaultAccess, allowed: list[str], denied: list[str]):
    return SimpleNamespace(
        provider=provider,
        default_access=default,
        allowed_tags=allowed,
        denied_tags=denied,
    )


def test_credential_gate_failure_short_circuits():
    m = _model("anthropic", DefaultAccess.open, [], [])
    r = evaluate_visibility(m, member_tags=set(), active_providers={"azure"})
    assert r["visible"] is False
    assert r["reason_chain"][0]["check"] == "credential_gate"
    assert r["reason_chain"][0]["pass"] is False
    # Short-circuit: should NOT evaluate further checks
    assert len(r["reason_chain"]) == 1


def test_open_no_deny_passes():
    m = _model("azure", DefaultAccess.open, [], [])
    r = evaluate_visibility(m, member_tags=set(), active_providers={"azure"})
    assert r["visible"] is True


def test_open_with_deny_hit_blocks():
    m = _model("azure", DefaultAccess.open, [], ["contractor"])
    r = evaluate_visibility(m, member_tags={"contractor"}, active_providers={"azure"})
    assert r["visible"] is False
    deny_check = next(c for c in r["reason_chain"] if c["check"] == "deny_tags")
    assert deny_check["pass"] is False


def test_restricted_allow_hit_passes():
    m = _model("azure", DefaultAccess.restricted, ["eng"], [])
    r = evaluate_visibility(m, member_tags={"eng"}, active_providers={"azure"})
    assert r["visible"] is True


def test_restricted_no_allow_hit_blocks():
    m = _model("azure", DefaultAccess.restricted, ["eng"], [])
    r = evaluate_visibility(m, member_tags={"pm"}, active_providers={"azure"})
    assert r["visible"] is False
    allow_check = next(c for c in r["reason_chain"] if c["check"] == "allow_tags")
    assert allow_check["pass"] is False


def test_deny_overrides_allow():
    m = _model("azure", DefaultAccess.restricted, ["eng"], ["contractor"])
    r = evaluate_visibility(
        m, member_tags={"eng", "contractor"}, active_providers={"azure"}
    )
    # Deny short-circuits before allow is evaluated
    assert r["visible"] is False
    deny_check = next(c for c in r["reason_chain"] if c["check"] == "deny_tags")
    assert deny_check["pass"] is False
