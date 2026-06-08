"""Phase 23 Foundational integration test (Postgres): migration 0018 adds the
additive `model_catalog.litellm_sync` column without regressing the catalog.

Drives real Alembic, asserts the column exists and an existing catalog row keeps
`litellm_sync` NULL. Skipped when no Postgres/Docker is available.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ai_api.config import get_settings
from ai_api.models import ModelCatalog


def _alembic_config(url: str):
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    return Config(os.path.join(root, "alembic.ini"))


def test_migration_0018_adds_litellm_sync_no_regression(postgres_url: str) -> None:
    from alembic import command

    async def wipe() -> None:
        engine = create_async_engine(postgres_url, poolclass=None)
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    async def seed_existing_model() -> None:
        engine = create_async_engine(postgres_url)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(UTC)
        async with sm() as s:
            s.add(
                ModelCatalog(
                    slug="azure/gpt-legacy",
                    provider="azure",
                    display_name="Legacy",
                    family="general",
                    description="",
                    modality_input=["text"],
                    modality_output=["text"],
                    capabilities=["chat"],
                    context_window=4096,
                    cost_tier="medium",
                    recommended_for=[],
                    tags=[],
                    example_request={},
                    official_doc_url=None,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            await s.commit()
        await engine.dispose()

    async def assert_after() -> None:
        engine = create_async_engine(postgres_url)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.connect() as conn:
            cols = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("model_catalog")}
            )
            assert "litellm_sync" in cols  # additive column present
        async with sm() as s:
            row = (
                await s.execute(select(ModelCatalog).where(ModelCatalog.slug == "azure/gpt-legacy"))
            ).scalar_one()
            assert row.litellm_sync is None  # existing rows untouched
        await engine.dispose()

    try:
        asyncio.run(wipe())
        command.upgrade(_alembic_config(postgres_url), "head")
        asyncio.run(seed_existing_model())
        asyncio.run(assert_after())
    finally:
        asyncio.run(wipe())
        get_settings.cache_clear()
