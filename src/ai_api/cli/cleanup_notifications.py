"""CLI entry point: delete notification records/buckets older than 30 days.

Designed to run as a K8s CronJob (Phase 13, FR-024 retention).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.models import NotificationDedupBucket, NotificationRecord
from ai_api.observability.logging import setup_logging

_RETENTION_DAYS = 30


async def _main() -> int:
    setup_logging()
    sm = get_sessionmaker()
    cutoff = datetime.now(UTC) - timedelta(days=_RETENTION_DAYS)
    async with sm() as session:
        try:
            rec_result = await session.execute(
                delete(NotificationRecord).where(NotificationRecord.created_at < cutoff)
            )
            bucket_result = await session.execute(
                delete(NotificationDedupBucket).where(
                    NotificationDedupBucket.window_end < cutoff
                )
            )
            await session.commit()
            print(
                f"cleanup_notifications: removed records={rec_result.rowcount} "
                f"buckets={bucket_result.rowcount}"
            )
            return 0
        except Exception as exc:
            await session.rollback()
            print(f"cleanup_notifications failed: {exc}", file=sys.stderr)
            return 1
        finally:
            await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
