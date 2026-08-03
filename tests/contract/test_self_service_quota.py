"""Bugfix: self-service default_quota (and token-quota columns) must accept values
above INT4's ~2.1e9 (e.g. 10e9) — Postgres INT4 overflowed → 500 ("更新失敗").
Columns widened to BIGINT + a sane API cap."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import BigInteger

from ai_api.models import Allocation, ModelCatalog, PoolConfig


def test_token_quota_columns_are_bigint() -> None:
    # The real guard: SQLite stores 64-bit regardless, so only asserting the column
    # type catches a regression to INT4 (which overflows on Postgres at 2.147e9).
    assert isinstance(Allocation.__table__.c.quota_tokens_per_month.type, BigInteger)
    assert isinstance(ModelCatalog.__table__.c.self_service_default_quota.type, BigInteger)
    assert isinstance(PoolConfig.__table__.c.total_tokens_per_month.type, BigInteger)


@pytest.mark.asyncio
async def test_self_service_accepts_10_billion(app_client: AsyncClient, admin_headers) -> None:
    # 10e9 passes body validation (would hit 404 for a missing model — NOT 422).
    r = await app_client.patch(
        "/admin/catalog/models/nonexistent-model/self-service",
        headers=admin_headers,
        json={"enabled": True, "default_quota": 10_000_000_000},
    )
    assert r.status_code == 404, r.text  # reached handler (not rejected by schema)


@pytest.mark.asyncio
async def test_self_service_caps_absurd_quota(app_client: AsyncClient, admin_headers) -> None:
    r = await app_client.patch(
        "/admin/catalog/models/nonexistent-model/self-service",
        headers=admin_headers,
        json={"enabled": True, "default_quota": 10**16},  # above the 1e15 cap
    )
    assert r.status_code == 422
