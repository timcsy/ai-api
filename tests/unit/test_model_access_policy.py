"""Phase 5 T038 / US3: pure-function access_policy_allows truth table."""
from __future__ import annotations

from types import SimpleNamespace

from ai_api.models import DefaultAccess
from ai_api.services.model_access import access_policy_allows


def _model(default: DefaultAccess, allowed: list[str], denied: list[str]):
    return SimpleNamespace(default_access=default, allowed_tags=allowed, denied_tags=denied)


def test_open_no_tags_passes() -> None:
    assert access_policy_allows(_model(DefaultAccess.open, [], []), set()) is True


def test_restricted_no_tags_blocks() -> None:
    assert access_policy_allows(_model(DefaultAccess.restricted, [], []), set()) is False


def test_restricted_allow_hit_passes() -> None:
    assert access_policy_allows(_model(DefaultAccess.restricted, ["eng"], []), {"eng"}) is True


def test_restricted_no_allow_hit_blocks() -> None:
    assert access_policy_allows(_model(DefaultAccess.restricted, ["eng"], []), {"pm"}) is False


def test_open_deny_blocks() -> None:
    assert access_policy_allows(_model(DefaultAccess.open, [], ["contractor"]), {"contractor"}) is False


def test_deny_overrides_allow() -> None:
    """Member with both allow-hit and deny-hit → deny wins."""
    assert (
        access_policy_allows(
            _model(DefaultAccess.restricted, ["eng"], ["contractor"]),
            {"eng", "contractor"},
        )
        is False
    )


def test_open_with_unrelated_tags_passes() -> None:
    assert access_policy_allows(_model(DefaultAccess.open, [], []), {"random"}) is True
