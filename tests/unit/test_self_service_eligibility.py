"""Phase 6 T012 / US2: pure self-service claim eligibility truth table."""
from __future__ import annotations

from types import SimpleNamespace

from ai_api.models import DefaultAccess
from ai_api.services.self_service import evaluate_claim_eligibility


def _model(*, enabled=True, default=DefaultAccess.open, allowed=None, denied=None, provider="azure"):
    return SimpleNamespace(
        provider=provider,
        self_service_enabled=enabled,
        default_access=default,
        allowed_tags=allowed or [],
        denied_tags=denied or [],
    )


def _eval(**kw):
    base = dict(
        member_active=True,
        model=_model(),
        member_tags=set(),
        active_providers={"azure"},
        has_active_self_alloc=False,
        reclaim_locked=False,
    )
    base.update(kw)
    return evaluate_claim_eligibility(**base)


def test_eligible_open_model():
    assert _eval()["eligible"] is True


def test_member_inactive():
    r = _eval(member_active=False)
    assert r["eligible"] is False and r["reason"] == "member_inactive"


def test_model_not_self_service():
    r = _eval(model=_model(enabled=False))
    assert r["eligible"] is False and r["reason"] == "model_not_self_service"


def test_model_forbidden_credential_gate():
    r = _eval(active_providers=set())  # no credential for provider
    assert r["eligible"] is False and r["reason"] == "model_forbidden"


def test_model_forbidden_restricted_no_tag():
    r = _eval(model=_model(default=DefaultAccess.restricted, allowed=["eng"]), member_tags=set())
    assert r["eligible"] is False and r["reason"] == "model_forbidden"


def test_model_forbidden_denied():
    r = _eval(model=_model(denied=["contractor"]), member_tags={"contractor"})
    assert r["eligible"] is False and r["reason"] == "model_forbidden"


def test_already_claimed():
    r = _eval(has_active_self_alloc=True)
    assert r["eligible"] is False and r["reason"] == "already_claimed"


def test_reclaim_locked():
    r = _eval(reclaim_locked=True)
    assert r["eligible"] is False and r["reason"] == "reclaim_locked"


def test_order_inactive_before_everything():
    # inactive member with also-locked + closed model → inactive wins (first check)
    r = _eval(member_active=False, model=_model(enabled=False), reclaim_locked=True)
    assert r["reason"] == "member_inactive"


def test_order_forbidden_before_already_claimed():
    # not allowed AND already has alloc → forbidden wins (structural before state)
    r = _eval(active_providers=set(), has_active_self_alloc=True)
    assert r["reason"] == "model_forbidden"
