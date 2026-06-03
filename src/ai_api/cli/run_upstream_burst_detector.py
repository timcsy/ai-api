"""CLI entry point for the upstream error-burst detector — runs as a K8s CronJob."""
from __future__ import annotations

import asyncio
import sys

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.observability.logging import setup_logging
from ai_api.services.notifier_hook import drain_notifier_tasks
from ai_api.services.upstream_burst_detector import detect_upstream_burst


async def _main() -> int:
    setup_logging()
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            decision = await detect_upstream_burst(session)
            await session.commit()
            # Ensure any fire-and-forget notifier task completes before the
            # short-lived cron process exits.
            await drain_notifier_tasks()
            if decision is not None:
                print(
                    f"upstream_burst_detector: burst detected, "
                    f"count={decision.failure_count} window={decision.window_minutes}min"
                )
            else:
                print("upstream_burst_detector: no burst")
            return 0
        except Exception as exc:
            await session.rollback()
            print(f"upstream_burst_detector failed: {exc}", file=sys.stderr)
            return 1
        finally:
            await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
