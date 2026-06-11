"""Phase 7 T004/T009/T014 / US1+US2+US3: admin price list endpoints.

Contract: specs/016-price-list-admin/contracts/admin-prices.yaml
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog, PriceList


async def _seed_model(slug: str, provider: str = "azure") -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug=slug, provider=provider, display_name=slug, family="x",
                description="", modality_input=["text"], modality_output=["text"],
                capabilities=[], context_window=1024, cost_tier="low",
                recommended_for=[], tags=[], example_request={}, official_doc_url=None,
                status="active", deprecation_note=None, created_at=now, updated_at=now,
            )
        )
        await s.commit()


async def _seed_price(provider: str, model: str, eff: str, inp: str = "0.0001") -> None:
    from ulid import ULID
    sm = get_sessionmaker()
    async with sm() as s:
        s.add(
            PriceList(
                id=str(ULID()), provider=provider, model=model,
                input_per_1k_tokens_usd=Decimal(inp),
                output_per_1k_tokens_usd=Decimal("0.0002"),
                effective_from=datetime.fromisoformat(eff),
                created_at=datetime.now(UTC), created_by="test", source_note="seed",
            )
        )
        await s.commit()


# ---------- US1: GET /admin/prices ----------

@pytest.mark.asyncio
async def test_list_priced_and_unpriced(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_model("azure/gpt-4o-mini")
    await _seed_model("azure/gpt-5.4-mini")  # unpriced
    await _seed_price("azure", "gpt-4o-mini", "2026-05-01T00:00:00+00:00")

    r = await app_client.get("/admin/prices", headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = {row["slug"]: row for row in r.json()}
    assert rows["azure/gpt-4o-mini"]["priced"] is True
    assert Decimal(rows["azure/gpt-4o-mini"]["current"]["input_per_1k"]) == Decimal("0.0001")
    assert rows["azure/gpt-5.4-mini"]["priced"] is False
    assert rows["azure/gpt-5.4-mini"]["current"] is None
    # key is prefix-stripped
    assert rows["azure/gpt-4o-mini"]["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_list_requires_admin(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/prices")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_surfaces_orphan_price(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # a price for a (provider, model) with no catalog model → listed as not-in-catalog
    await _seed_price("anthropic", "claude-x", "2026-05-01T00:00:00+00:00")
    rows = {row["slug"]: row for row in (await app_client.get("/admin/prices", headers=admin_headers)).json()}
    assert "anthropic/claude-x" in rows
    assert rows["anthropic/claude-x"]["in_catalog"] is False
    assert rows["anthropic/claude-x"]["priced"] is True


# ---------- US2: POST /admin/prices ----------

@pytest.mark.asyncio
async def test_create_version(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_model("azure/gpt-5.4-mini")
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure", "model": "gpt-5.4-mini",
              "input_per_1k": "0.0003", "output_per_1k": "0.0012",
              "effective_from": "2026-05-01T00:00:00+00:00", "source_note": "manual"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_current"] is True
    # now listed as priced
    rows = {x["slug"]: x for x in (await app_client.get("/admin/prices", headers=admin_headers)).json()}
    assert rows["azure/gpt-5.4-mini"]["priced"] is True


# Phase 11 — cached input price flows through create + list + history
@pytest.mark.asyncio
async def test_create_with_cached_input_price(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_model("azure/gpt-5.4")
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure", "model": "gpt-5.4",
              "input_per_1k": "0.0003", "output_per_1k": "0.0012",
              "cached_input_per_1k": "0.0000375",
              "effective_from": "2026-05-01T00:00:00+00:00"},
    )
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["cached_input_per_1k"]) == Decimal("0.0000375")
    # current price surfaces cached
    rows = {x["slug"]: x for x in (await app_client.get("/admin/prices", headers=admin_headers)).json()}
    assert Decimal(rows["azure/gpt-5.4"]["current"]["cached_input_per_1k"]) == Decimal("0.0000375")
    # history surfaces cached
    hist = (await app_client.get(
        "/admin/prices/history?provider=azure&model=gpt-5.4", headers=admin_headers
    )).json()
    assert Decimal(hist[0]["cached_input_per_1k"]) == Decimal("0.0000375")


@pytest.mark.asyncio
async def test_create_without_cached_is_null(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_model("azure/no-cache")
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure", "model": "no-cache", "input_per_1k": "0.001",
              "output_per_1k": "0.002", "effective_from": "2026-05-01T00:00:00+00:00"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["cached_input_per_1k"] is None


@pytest.mark.asyncio
async def test_create_duplicate_409(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    body = {"provider": "azure", "model": "dup-m", "input_per_1k": "0.001",
            "output_per_1k": "0.002", "effective_from": "2026-05-01T00:00:00+00:00"}
    r1 = await app_client.post("/admin/prices", headers=admin_headers, json=body)
    assert r1.status_code == 201
    r2 = await app_client.post("/admin/prices", headers=admin_headers, json=body)
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"]["code"] == "duplicate_version"


@pytest.mark.asyncio
async def test_create_negative_422(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure", "model": "neg-m", "input_per_1k": "-0.001",
              "output_per_1k": "0.002", "effective_from": "2026-05-01T00:00:00+00:00"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "invalid_price"


# ---------- US3: GET /admin/prices/history ----------

@pytest.mark.asyncio
async def test_history(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed_price("azure", "hist-m", "2026-05-01T00:00:00+00:00")
    await _seed_price("azure", "hist-m", "2099-01-01T00:00:00+00:00")  # future
    r = await app_client.get(
        "/admin/prices/history", headers=admin_headers,
        params={"provider": "azure", "model": "hist-m"},
    )
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) == 2
    # newest first
    assert versions[0]["effective_from"].startswith("2099")
    # exactly one current; the future one is not current
    current = [v for v in versions if v["is_current"]]
    assert len(current) == 1
    assert current[0]["effective_from"].startswith("2026-05-01")


# ---------- Phase 29 ② (040): per-unit (page) price ----------

@pytest.mark.asyncio
async def test_create_per_page_price(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure_ai", "model": "mistral-document-ai",
              "input_per_1k": "0", "output_per_1k": "0",
              "price_unit": "page", "price_per_unit": "0.003",
              "effective_from": "2026-06-01T00:00:00+00:00"},
    )
    assert r.status_code == 201, r.text
    hist = (await app_client.get(
        "/admin/prices/history?provider=azure_ai&model=mistral-document-ai",
        headers=admin_headers,
    )).json()
    assert hist[0]["price_unit"] == "page"
    assert Decimal(hist[0]["price_per_unit"]) == Decimal("0.003")


@pytest.mark.asyncio
async def test_per_unit_requires_price(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure_ai", "model": "ocr-y",
              "input_per_1k": "0", "output_per_1k": "0",
              "price_unit": "page",  # no price_per_unit
              "effective_from": "2026-06-01T00:00:00+00:00"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "bad_request"
