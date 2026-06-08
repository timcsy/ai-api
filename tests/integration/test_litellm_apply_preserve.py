"""Phase 25 (FR-006 / SC-004): adopting litellm `capabilities` MUST merge-preserve
the responses* markers (axis ③), so a sync never silently wipes admin's setting."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog
from ai_api.services import responses_support as rs


async def _seed_gpt4o_with_responses() -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug="azure/gpt-4o",
                provider="azure",
                display_name="GPT-4o",
                family="gpt-4o",
                description="",
                modality_input=["text"],
                modality_output=["text"],
                # admin had marked it responses-available via manual override:
                capabilities=["chat", rs.RESPONSES, rs.RESPONSES_MANUAL],
                context_window=4096,
                cost_tier="medium",
                recommended_for=[],
                tags=[],
                example_request={},
                official_doc_url=None,
                status="active",
                deprecation_note=None,
                created_at=now,
                updated_at=now,
                litellm_sync={
                    "base_model_key": "azure/gpt-4o",
                    "imported_version": "0.0.0",
                    "field_sources": {"capabilities": "manual"},
                    "snapshot": {},
                },
            )
        )
        await s.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_litellm_apply_capabilities_preserves_responses_markers(
    app_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    await _seed_gpt4o_with_responses()

    # Force offline → bundled registry (deterministic).
    with patch("ai_api.services.litellm_registry.fetch_latest", return_value=None):
        r = await app_client.post(
            "/admin/catalog/models/azure/gpt-4o/litellm-apply",
            headers=admin_headers,
            json={"fields": ["capabilities"]},
        )
    assert r.status_code == 200, r.text

    sm = get_sessionmaker()
    async with sm() as s:
        m = await s.get(ModelCatalog, "azure/gpt-4o")
        assert m is not None
        caps = list(m.capabilities)

    # responses* markers preserved (merge-preserve)
    assert rs.RESPONSES in caps
    assert rs.RESPONSES_MANUAL in caps
    assert rs.get_support(caps)["state"] == "available"
    # litellm-derived caps were applied (gpt-4o supports function-calling/vision)
    assert "function-calling" in caps
    # litellm itself contributed NO responses marker
    assert caps.count(rs.RESPONSES) == 1
