"""Unit tests for quota service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ai_api.services.quota import current_month_start_utc, is_over_quota


def test_current_month_start_anchors_to_utc_first():
    n = datetime(2026, 5, 15, 12, 30, 45, tzinfo=UTC)
    assert current_month_start_utc(n) == datetime(2026, 5, 1, tzinfo=UTC)


def test_current_month_start_already_at_month_boundary():
    n = datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC)
    assert current_month_start_utc(n) == n


@dataclass
class _Alloc:
    quota_tokens_per_month: int | None


def test_unlimited_quota_never_over():
    assert is_over_quota(_Alloc(quota_tokens_per_month=None), 999_999_999) is False


def test_quota_boundary_just_under():
    assert is_over_quota(_Alloc(quota_tokens_per_month=100), 99) is False


def test_quota_boundary_exact():
    # usage == quota → over (>= rule)
    assert is_over_quota(_Alloc(quota_tokens_per_month=100), 100) is True


def test_quota_boundary_over():
    assert is_over_quota(_Alloc(quota_tokens_per_month=100), 101) is True
