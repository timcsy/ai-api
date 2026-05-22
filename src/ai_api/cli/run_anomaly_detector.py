"""CLI entry point for the anomaly detector — designed to run as a K8s CronJob."""
from __future__ import annotations

import asyncio
import sys

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.observability.logging import setup_logging
from ai_api.services.anomaly import detect_and_quarantine


async def _main() -> int:
    setup_logging()
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            decisions = await detect_and_quarantine(session)
            await session.commit()
            print(f"anomaly_detector: scanned, quarantined={len(decisions)}")
            return 0
        except Exception as exc:
            await session.rollback()
            print(f"anomaly_detector failed: {exc}", file=sys.stderr)
            return 1
        finally:
            await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
