"""Phase 7 T003 / US1: pure current-version selection (point-in-time)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from ai_api.services.pricing import select_current_version


def _v(eff: str, inp: str = "0.001"):
    return SimpleNamespace(
        effective_from=datetime.fromisoformat(eff),
        input_per_1k_tokens_usd=Decimal(inp),
        output_per_1k_tokens_usd=Decimal("0.002"),
    )


NOW = datetime(2026, 5, 26, tzinfo=UTC)


def test_no_versions_returns_none():
    assert select_current_version([], NOW) is None


def test_single_past_version():
    v = _v("2026-05-01T00:00:00+00:00")
    assert select_current_version([v], NOW) is v


def test_latest_past_wins():
    older = _v("2026-05-01T00:00:00+00:00")
    newer = _v("2026-05-20T00:00:00+00:00")
    assert select_current_version([older, newer], NOW) is newer


def test_future_version_excluded():
    past = _v("2026-05-01T00:00:00+00:00")
    future = _v("2026-06-01T00:00:00+00:00")
    # current must be the past one, not the future-dated
    assert select_current_version([past, future], NOW) is past


def test_all_future_returns_none():
    future = _v("2026-06-01T00:00:00+00:00")
    assert select_current_version([future], NOW) is None


def test_unsorted_input_ok():
    a = _v("2026-05-20T00:00:00+00:00")
    b = _v("2026-05-01T00:00:00+00:00")
    c = _v("2026-05-10T00:00:00+00:00")
    assert select_current_version([a, b, c], NOW) is a
