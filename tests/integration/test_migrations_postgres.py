"""Run the full Alembic migration chain against a real Postgres.

The prod deploy runs `alembic upgrade head` on Postgres; our other migration
checks only used SQLite, which masked an ordering bug in 0002 (dropping a column
before its dependent index — Postgres auto-drops the index, SQLite's batch
table-copy didn't). This test reproduces the prod path so such bugs are caught.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.integration


@pytest.fixture
def fresh_pg_url() -> str:
    try:
        from testcontainers.postgres import PostgresContainer
    except Exception as e:  # pragma: no cover
        pytest.skip(f"testcontainers not available: {e}")
    with PostgresContainer("postgres:15-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()


def test_alembic_upgrade_head_on_postgres(fresh_pg_url: str) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": fresh_pg_url,
        "PROVIDER_KEY_ENC_KEY": "wG4iqV3qxGqQfp_8ARDqVU93G8YzxBOFnHTL98_3l9I=",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic upgrade head failed on Postgres:\n{result.stderr}"
