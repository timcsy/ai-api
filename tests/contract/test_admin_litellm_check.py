"""Phase 23 US4: check LiteLLM updates (live fetch + bundled fallback) and diff."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import litellm
import pytest
from httpx import AsyncClient


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
    base["max_input_tokens"] = 200000          # context changed
    base["input_cost_per_token"] = 3e-06        # price changed → 0.003/1k
    return {"azure/gpt-4o": base}


@pytest.mark.asyncio
async def test_check_lists_diffs_from_live(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _create_linked(app_client, admin_headers)
    with patch("ai_api.api.admin_catalog.litellm_registry.fetch_latest",
               new=AsyncMock(return_value=_bumped_map())):
        r = await app_client.post("/admin/catalog/models/azure/gpt-4o/litellm-check", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "live"
    by_field = {d["field"]: d for d in body["diffs"]}
    assert by_field["context_window"]["latest"] == 200000
    assert by_field["context_window"]["changed"] is True
    assert by_field["context_window"]["source"] == "litellm"
    assert by_field["price.input_per_1k"]["latest"] == "0.003"
    assert by_field["price.input_per_1k"]["changed"] is True


@pytest.mark.asyncio
async def test_check_falls_back_to_bundled_on_failure(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _create_linked(app_client, admin_headers)
    with patch("ai_api.api.admin_catalog.litellm_registry.fetch_latest",
               new=AsyncMock(return_value=None)):  # live fetch failed/timed out
        r = await app_client.post("/admin/catalog/models/azure/gpt-4o/litellm-check", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "bundled-fallback"
    assert any(d["field"] == "context_window" for d in body["diffs"])  # still diffs against bundled
