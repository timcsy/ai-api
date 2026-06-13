"""Unit tests for quota service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ai_api.services.quota import current_month_start_utc, is_over_cost_quota, is_over_quota


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


# --- Phase 33 (046): cost-based quota ---------------------------------------
@dataclass
class _CostAlloc:
    quota_cost_usd_per_month: Decimal | None


def test_cost_unlimited_never_over():
    assert is_over_cost_quota(_CostAlloc(None), Decimal("999.99")) is False


def test_cost_boundary_just_under():
    assert is_over_cost_quota(_CostAlloc(Decimal("5")), Decimal("4.999999")) is False


def test_cost_boundary_exact_is_over():
    # spent == cap → over (>= rule, mirrors token quota)
    assert is_over_cost_quota(_CostAlloc(Decimal("5")), Decimal("5")) is True


def test_cost_boundary_over():
    assert is_over_cost_quota(_CostAlloc(Decimal("5")), Decimal("5.20")) is True


def test_cost_zero_cap_blocks_any_spend():
    assert is_over_cost_quota(_CostAlloc(Decimal("0")), Decimal("0")) is True
