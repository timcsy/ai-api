"""Phase 23 US1/US2/US3: create a catalog model aligned with LiteLLM —
bring-in metadata + suggested price, base-model borrowing, source provenance."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import PriceList


async def _suggest(client: AsyncClient, admin: dict[str, str], key: str) -> dict:
    return (await client.get(f"/admin/catalog/litellm/suggest/{key}", headers=admin)).json()


@pytest.mark.asyncio
async def test_create_with_litellm_bring_in(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    s = await _suggest(app_client, admin_headers, "azure/gpt-4o")
    payload = {
        "slug": "azure/gpt-4o",
        "provider": "azure",
        "display_name": "GPT-4o",
        "base_model_key": "azure/gpt-4o",
        **s["metadata"],
        "suggested_price": s["suggested_price"],
    }
    r = await app_client.post("/admin/catalog/models", headers=admin_headers, json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    sync = body["litellm_sync"]
    assert sync is not None
    assert sync["base_model_key"] == "azure/gpt-4o"
    assert sync["field_sources"]["context_window"] == "litellm"
    assert sync["snapshot"]["context_window"] == 128000
    # suggested price seeded as a versioned row with litellm source_note.
    sm = get_sessionmaker()
    async with sm() as db:
        rows = (await db.execute(select(PriceList).where(PriceList.model == "gpt-4o"))).scalars().all()
        assert len(rows) == 1
        assert rows[0].source_note.startswith("litellm@")
        assert Decimal(str(rows[0].input_per_1k_tokens_usd)) == Decimal("0.0025")


@pytest.mark.asyncio
async def test_create_custom_deployment_borrows_base_model(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # US2: custom slug not in registry borrows metadata from a base model key.
    s = await _suggest(app_client, admin_headers, "azure/gpt-4o")
    payload = {
        "slug": "azure/gpt-5.4",  # our custom deployment, not a litellm key
        "provider": "azure",
        "display_name": "GPT-5.4 (Azure deployment)",
        "base_model_key": "azure/gpt-4o",
        **s["metadata"],
        # no suggested_price → admin sets price themselves
    }
    r = await app_client.post("/admin/catalog/models", headers=admin_headers, json=payload)
    assert r.status_code == 201, r.text
    sync = r.json()["litellm_sync"]
    assert sync["base_model_key"] == "azure/gpt-4o"
    assert sync["field_sources"]["context_window"] == "borrowed"  # borrowed, slug stays custom
    # no price row auto-created
    sm = get_sessionmaker()
    async with sm() as db:
        rows = (await db.execute(select(PriceList).where(PriceList.model == "gpt-5.4"))).scalars().all()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_edited_field_marked_manual(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # US3: a field the admin overrides at create time is marked manual.
    s = await _suggest(app_client, admin_headers, "azure/gpt-4o")
    payload = {
        "slug": "azure/gpt-4o",
        "provider": "azure",
        "display_name": "GPT-4o",
        "base_model_key": "azure/gpt-4o",
        **s["metadata"],
        "context_window": 64000,  # overridden → manual
    }
    r = await app_client.post("/admin/catalog/models", headers=admin_headers, json=payload)
    assert r.status_code == 201, r.text
    fs = r.json()["litellm_sync"]["field_sources"]
    assert fs["context_window"] == "manual"
    assert fs["capabilities"] == "litellm"  # untouched stays litellm


@pytest.mark.asyncio
async def test_patch_syncable_field_turns_manual(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # US3: editing a synced field after create flips its source to manual.
    s = await _suggest(app_client, admin_headers, "azure/gpt-4o")
    await app_client.post(
        "/admin/catalog/models",
        headers=admin_headers,
        json={"slug": "azure/gpt-4o", "provider": "azure", "display_name": "GPT-4o",
              "base_model_key": "azure/gpt-4o", **s["metadata"]},
    )
    r = await app_client.patch(
        "/admin/catalog/models/azure/gpt-4o", headers=admin_headers, json={"context_window": 32000}
    )
    assert r.status_code == 200, r.text
    sync = r.json()["litellm_sync"]
    assert sync["field_sources"]["context_window"] == "manual"
    assert sync["snapshot"]["context_window"] == 128000  # snapshot preserved
