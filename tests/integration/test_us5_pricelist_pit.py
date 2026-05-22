"""US5 integration: point-in-time billing.

Load v1 prices → make calls → record cost X.
Load v2 prices (2x) → make new calls → new cost 2X; v1 records unchanged.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ai_api.db import get_sessionmaker
from ai_api.services.pricing import lookup_price_for_call

ROOT = Path(__file__).resolve().parents[2]


async def _load_yaml(path: Path) -> int:
    import sys

    sys.argv = ["load_prices", str(path)]
    from ai_api.cli.load_prices import _load

    return await _load(path)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_load_two_versions_and_point_in_time(app_client) -> None:
    n1 = await _load_yaml(ROOT / "deploy" / "prices" / "azure-2026-05.yaml")
    assert n1 == 2

    sm = get_sessionmaker()
    async with sm() as s:
        # Lookup for a call at 2026-05-15 → should hit v1 (input=0.000150)
        p_may = await lookup_price_for_call(
            s,
            provider="azure",
            model="gpt-4o-mini",
            call_time=datetime(2026, 5, 15, tzinfo=UTC),
        )
        assert p_may is not None
        assert p_may.input_per_1k == Decimal("0.000150")

    n2 = await _load_yaml(ROOT / "deploy" / "prices" / "azure-2026-06-double.yaml")
    assert n2 == 2

    async with sm() as s:
        # 2026-05-15 still hits v1
        p_may = await lookup_price_for_call(
            s,
            provider="azure",
            model="gpt-4o-mini",
            call_time=datetime(2026, 5, 15, tzinfo=UTC),
        )
        assert p_may.input_per_1k == Decimal("0.000150")

        # 2026-06-15 hits v2 (doubled)
        p_jun = await lookup_price_for_call(
            s,
            provider="azure",
            model="gpt-4o-mini",
            call_time=datetime(2026, 6, 15, tzinfo=UTC),
        )
        assert p_jun.input_per_1k == Decimal("0.000300")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unique_violation_aborts_load(app_client) -> None:
    await _load_yaml(ROOT / "deploy" / "prices" / "azure-2026-05.yaml")
    # Loading the same file again should fail (UNIQUE on provider/model/effective_from)
    with pytest.raises(SystemExit):
        await _load_yaml(ROOT / "deploy" / "prices" / "azure-2026-05.yaml")
