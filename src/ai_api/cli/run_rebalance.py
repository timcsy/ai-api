"""CLI entry point for the monthly quota-pool rebalance.

Run from a Kubernetes CronJob; logs outcome to stdout. Exit codes:
- 0: success or cron-dedup no-op
- 1: known business failure (pool disabled/idle/exhausted)
- 2: unexpected error
"""
from __future__ import annotations

import asyncio
import sys

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.observability.logging import setup_logging
from ai_api.services.quota_pool import (
    PoolDisabledError,
    PoolExhaustedByReservedError,
    PoolIdleError,
    RebalanceConservationError,
    apply_rebalance,
)


async def _main() -> int:
    setup_logging()
    sm = get_sessionmaker()
    try:
        async with sm() as s:
            try:
                outcome = await apply_rebalance(s, trigger="cron")
                await s.commit()
            except (
                PoolDisabledError,
                PoolIdleError,
                PoolExhaustedByReservedError,
            ) as exc:
                await s.commit()  # preserve audit row
                print(f"run_rebalance: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 1
            except RebalanceConservationError as exc:
                await s.rollback()
                print(f"run_rebalance: conservation failed: {exc}", file=sys.stderr)
                return 2
        if outcome.log is None:
            print(f"run_rebalance: skipped — {outcome.skipped_reason}")
        else:
            print(
                f"run_rebalance: log_id={outcome.log.id} "
                f"scanned={outcome.log.scanned} changed={outcome.log.changed} "
                f"T={outcome.log.T_after}"
            )
    finally:
        await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
