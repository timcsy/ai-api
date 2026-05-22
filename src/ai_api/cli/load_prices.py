"""CLI: load PriceList entries from a YAML file (append-only, point-in-time)."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.models import PriceList
from ai_api.observability.logging import setup_logging


def _parse_yaml(path: Path) -> tuple[datetime, str | None, list[dict[str, object]]]:
    raw = yaml.safe_load(path.read_text())
    eff = raw["effective_from"]
    eff_dt = datetime.fromisoformat(eff.replace("Z", "+00:00")) if isinstance(eff, str) else eff
    if eff_dt.tzinfo is None:
        eff_dt = eff_dt.replace(tzinfo=UTC)
    return eff_dt, raw.get("source_note"), list(raw["prices"])


async def _load(path: Path) -> int:
    eff, source_note, entries = _parse_yaml(path)
    sm = get_sessionmaker()
    created_by = f"cli:{os.environ.get('USER', 'unknown')}"
    inserted = 0
    async with sm() as session:
        try:
            for entry in entries:
                row = PriceList(
                    id=str(ULID()),
                    provider=entry["provider"],
                    model=entry["model"],
                    input_per_1k_tokens_usd=Decimal(str(entry["input_per_1k_tokens_usd"])),
                    output_per_1k_tokens_usd=Decimal(str(entry["output_per_1k_tokens_usd"])),
                    effective_from=eff,
                    created_at=datetime.now(UTC),
                    created_by=created_by,
                    source_note=source_note,
                )
                session.add(row)
            await session.commit()
            inserted = len(entries)
        except IntegrityError as exc:
            await session.rollback()
            print(f"load_prices: UNIQUE violation: {exc.orig}", file=sys.stderr)
            raise SystemExit(1) from exc
    return inserted


async def _main() -> int:
    setup_logging()
    if len(sys.argv) != 2:
        print("Usage: python -m ai_api.cli.load_prices <yaml-path>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"load_prices: file not found: {path}", file=sys.stderr)
        return 2
    try:
        n = await _load(path)
    finally:
        await dispose_engine()
    print(f"loaded {n} entries from {path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
