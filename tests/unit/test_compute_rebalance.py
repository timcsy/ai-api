"""Unit tests for the pure `compute_rebalance` function (Phase 3c US1)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_api.services.quota_pool import (
    PoolExhaustedByReservedError,
    PoolMember,
    compute_rebalance,
    previous_month_range_utc,
)


def _members(*entries: tuple[str, int]) -> list[PoolMember]:
    return [PoolMember(allocation_id=i, usage_last_month=u) for i, u in entries]


def test_empty_pool_returns_empty() -> None:
    assert compute_rebalance(T=1000, floor=100, reserved_total=0, pool=[]) == []


def test_general_5_3_2_ratio() -> None:
    # Spec SC-001: T=1000, floor=100, usage 5:3:2 → 450/310/240
    pool = _members(("A", 5), ("B", 3), ("C", 2))
    out = compute_rebalance(T=1000, floor=100, reserved_total=0, pool=pool)
    quotas = {r.allocation_id: r.new_quota for r in out}
    assert quotas == {"A": 450, "B": 310, "C": 240}
    assert sum(quotas.values()) == 1000


def test_cold_start_even_split() -> None:
    pool = _members(("X", 0), ("Y", 0), ("Z", 0))
    out = compute_rebalance(T=900, floor=100, reserved_total=0, pool=pool)
    assert sum(r.new_quota for r in out) == 900
    assert all(r.reason == "first_round" for r in out)


def test_zero_usage_member_only_gets_floor() -> None:
    # B has 0 usage; bonus goes only to A and C.
    pool = _members(("A", 100), ("B", 0), ("C", 100))
    out = compute_rebalance(T=1000, floor=100, reserved_total=0, pool=pool)
    quotas = {r.allocation_id: r.new_quota for r in out}
    assert quotas["B"] == 100  # floor only
    assert quotas["A"] + quotas["C"] == 900
    # SC-001 style: total conserved
    assert sum(quotas.values()) == 1000


def test_leftover_goes_to_highest_usage() -> None:
    # bonus=300, usage 7+3+3=13; ints would lose 1 token; goes to A (max).
    pool = _members(("A", 7), ("B", 3), ("C", 3))
    out = compute_rebalance(T=600, floor=100, reserved_total=0, pool=pool)
    # bonus_pool = 600-300 = 300; shares = floor(300*7/13)=161, floor(300*3/13)=69 ×2 = 299 → +1 to A
    quotas = {r.allocation_id: r.new_quota for r in out}
    assert quotas == {"A": 100 + 162, "B": 100 + 69, "C": 100 + 69}
    assert sum(quotas.values()) == 600


def test_leftover_tie_breaks_by_id_lex_max() -> None:
    # Same usage → leftover goes to id "Z" (lex-max).
    pool = _members(("A", 5), ("Z", 5))
    out = compute_rebalance(T=300, floor=100, reserved_total=0, pool=pool)
    # bonus=100; shares 50/50 exactly → no leftover; should be 150/150
    quotas = {r.allocation_id: r.new_quota for r in out}
    assert quotas == {"A": 150, "Z": 150}
    # Force a leftover: bonus=101
    pool2 = _members(("A", 5), ("Z", 5))
    out2 = compute_rebalance(T=301, floor=100, reserved_total=0, pool=pool2)
    quotas2 = {r.allocation_id: r.new_quota for r in out2}
    assert quotas2["Z"] == 151
    assert quotas2["A"] == 150
    assert sum(quotas2.values()) == 301


def test_reserved_total_reduces_distributable() -> None:
    # T=1000, reserved=500 → distributable=500
    pool = _members(("A", 1), ("B", 1))
    out = compute_rebalance(T=1000, floor=100, reserved_total=500, pool=pool)
    quotas = {r.allocation_id: r.new_quota for r in out}
    # bonus = 500 - 200 = 300; 150 each
    assert quotas == {"A": 250, "B": 250}
    assert sum(quotas.values()) + 500 == 1000


def test_pool_exhausted_when_floor_too_high() -> None:
    pool = _members(("A", 1), ("B", 1), ("C", 1))
    with pytest.raises(PoolExhaustedByReservedError):
        compute_rebalance(T=200, floor=100, reserved_total=0, pool=pool)


def test_pool_exhausted_when_reserved_too_high() -> None:
    pool = _members(("A", 1))
    with pytest.raises(PoolExhaustedByReservedError):
        compute_rebalance(T=500, floor=100, reserved_total=450, pool=pool)


def test_previous_month_range_basic() -> None:
    now = datetime(2026, 5, 22, 10, 30, tzinfo=UTC)
    prev, this = previous_month_range_utc(now)
    assert prev == datetime(2026, 4, 1, tzinfo=UTC)
    assert this == datetime(2026, 5, 1, tzinfo=UTC)


def test_previous_month_range_year_boundary() -> None:
    now = datetime(2026, 1, 5, tzinfo=UTC)
    prev, this = previous_month_range_utc(now)
    assert prev == datetime(2025, 12, 1, tzinfo=UTC)
    assert this == datetime(2026, 1, 1, tzinfo=UTC)
