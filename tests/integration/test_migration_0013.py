"""Phase 11 T003: schema for Responses API token breakdown + stored_responses.

Docker-free schema assertions via SQLite create_all (experience: prefer Docker-free).
Full Postgres up/down reversibility is exercised by the alembic CI run.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from ai_api.db import Base

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_schema_has_responses_columns_and_table(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'s.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _check(sync_conn) -> dict[str, set[str]]:
            insp = inspect(sync_conn)
            return {
                "call_records": {c["name"] for c in insp.get_columns("call_records")},
                "price_list": {c["name"] for c in insp.get_columns("price_list")},
                "tables": set(insp.get_table_names()),
            }

        info = await conn.run_sync(_check)
    await engine.dispose()

    assert {"reasoning_tokens", "cached_tokens"} <= info["call_records"]
    assert "cached_input_per_1k_tokens_usd" in info["price_list"]
    assert "stored_responses" in info["tables"]


def test_migration_0013_revision_chain() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("0013_responses_api")
    assert rev is not None
    assert rev.down_revision == "0012_self_service"
