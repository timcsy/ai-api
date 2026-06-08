"""Phase 23 US4: selectively apply LiteLLM updates; price appends a version,
manual fields are never overwritten."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import litellm
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog, PriceList


async def _create_linked(client: AsyncClient, admin: dict[str, str]) -> None:
    s = (await client.get("/admin/catalog/litellm/suggest/azure/gpt-4o", headers=admin)).json()
    await client.post(
        "/admin/catalog/models",
        headers=admin,
        json={"slug": "azure/gpt-4o", "provider": "azure", "display_name": "GPT-4o",
              "base_model_key": "azure/gpt-4o", **s["metadata"], "suggested_price": s["suggested_price"]},
    )


def _bumped_map() -> dict:
    base = dict(litellm.model_cost["azure/gpt-4o"])
    base["max_input_tokens"] = 200000
    base["input_cost_per_token"] = 3e-06
    return {"azure/gpt-4o": base}


@pytest.mark.asyncio
async def test_apply_metadata_field_updates_and_snapshot(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _create_linked(app_client, admin_headers)
    with patch("ai_api.api.admin_catalog.litellm_registry.fetch_latest",
               new=AsyncMock(return_value=_bumped_map())):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-4o/litellm-apply",
            headers=admin_headers, json={"fields": ["context_window"]},
        )
    assert r.status_code == 200, r.text
    sm = get_sessionmaker()
    async with sm() as db:
        m = await db.get(ModelCatalog, "azure/gpt-4o")
        assert m.context_window == 200000
        assert m.litellm_sync["snapshot"]["context_window"] == 200000
        assert m.litellm_sync["field_sources"]["context_window"] == "litellm"


@pytest.mark.asyncio
async def test_apply_price_appends_version(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _create_linked(app_client, admin_headers)
    with patch("ai_api.api.admin_catalog.litellm_registry.fetch_latest",
               new=AsyncMock(return_value=_bumped_map())):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-4o/litellm-apply",
            headers=admin_headers, json={"fields": ["price.input_per_1k"]},
        )
    assert r.status_code == 200, r.text
    sm = get_sessionmaker()
    async with sm() as db:
        rows = (await db.execute(select(PriceList).where(PriceList.model == "gpt-4o"))).scalars().all()
        assert len(rows) == 2  # original (0.0025) + appended (0.003); old kept
        newest = max(rows, key=lambda p: p.effective_from)
        assert Decimal(str(newest.input_per_1k_tokens_usd)) == Decimal("0.003")
        assert newest.source_note.startswith("litellm@")


@pytest.mark.asyncio
async def test_apply_skips_manual_field(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # Override context_window at create → manual → apply must NOT overwrite it.
    s = (await app_client.get("/admin/catalog/litellm/suggest/azure/gpt-4o", headers=admin_headers)).json()
    await app_client.post(
        "/admin/catalog/models",
        headers=admin_headers,
        json={"slug": "azure/gpt-4o", "provider": "azure", "display_name": "GPT-4o",
              "base_model_key": "azure/gpt-4o", **s["metadata"], "context_window": 50000},
    )
    with patch("ai_api.api.admin_catalog.litellm_registry.fetch_latest",
               new=AsyncMock(return_value=_bumped_map())):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-4o/litellm-apply",
            headers=admin_headers, json={"fields": ["context_window"]},
        )
    assert r.status_code == 200
    sm = get_sessionmaker()
    async with sm() as db:
        m = await db.get(ModelCatalog, "azure/gpt-4o")
        assert m.context_window == 50000  # manual value untouched
