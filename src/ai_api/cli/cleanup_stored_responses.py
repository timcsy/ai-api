"""CLI entry point: delete expired stored_responses — designed to run as a K8s CronJob."""
from __future__ import annotations

import asyncio
import sys

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.observability.logging import setup_logging
from ai_api.services.stored_responses import StoredResponseService


async def _main() -> int:
    setup_logging()
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            removed = await StoredResponseService(session).cleanup_expired()
            await session.commit()
            print(f"cleanup_stored_responses: removed={removed}")
            return 0
        except Exception as exc:
            await session.rollback()
            print(f"cleanup_stored_responses failed: {exc}", file=sys.stderr)
            return 1
        finally:
            await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
