"""Phase 7 T010 / US2: pricing admin flow — cost > 0 after pricing; point-in-time."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


def _stub() -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "test",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000},
    }


async def _seed_model(slug: str = "azure/pl-flow") -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug=slug, provider="azure", display_name="PL", family="x",
                description="", modality_input=["text"], modality_output=["text"],
                capabilities=["chat"], context_window=1024, cost_tier="low",
                recommended_for=[], tags=[], example_request={}, official_doc_url=None,
                status="active", deprecation_note=None, created_at=now, updated_at=now,
                default_access="open", allowed_tags=[], denied_tags=[],
            )
        )
        await s.commit()


async def _call(client: AsyncClient, token: str, slug: str) -> int:
    with patch("litellm.acompletion", return_value=_stub()):
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": slug, "messages": [{"role": "user", "content": "hi"}]},
        )
    return r.status_code


async def _costs(member_id: str) -> list:
    from sqlalchemy import select

    from ai_api.models import Allocation, CallRecord

    sm = get_sessionmaker()
    async with sm() as s:
        alloc_ids = (
            await s.execute(select(Allocation.id).where(Allocation.member_id == member_id))
        ).scalars().all()
        rows = (
            await s.execute(
                select(CallRecord)
                .where(CallRecord.allocation_id.in_(alloc_ids))
                .order_by(CallRecord.started_at)
            )
        ).scalars().all()
    return [r.cost_usd for r in rows]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pricing_admin_flow(
    app_client: AsyncClient, admin_headers: dict[str, str], make_member, make_provider_credential
) -> None:
    await make_provider_credential(provider="azure", api_key="sk-az-pl")
    await _seed_model()
    member = await make_member("pl@x.com")
    created = await app_client.post(
        "/admin/allocations", headers=admin_headers,
        json={"member_id": member, "resource_model": "azure/pl-flow"},
    )
    token = created.json()["token"]

    # 1. unpriced model → call records cost None
    assert await _call(app_client, token, "azure/pl-flow") == 200
    costs = await _costs(member)
    assert costs[-1] is None

    # 2. admin adds a price (effective in the past) → next call has cost > 0
    r = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure", "model": "pl-flow", "input_per_1k": "0.0030",
              "output_per_1k": "0.0060", "effective_from": "2026-05-01T00:00:00+00:00"},
    )
    assert r.status_code == 201, r.text
    assert await _call(app_client, token, "azure/pl-flow") == 200
    costs = await _costs(member)
    # 1000 prompt + 1000 completion tokens → (1*0.003)+(1*0.006) = 0.009
    assert costs[-1] is not None and costs[-1] > 0
    second_cost = costs[-1]

    # 3. point-in-time: the FIRST (unpriced) call's stored cost is still None
    assert costs[0] is None

    # 4. add a later-effective doubled price → newest call ~2x the priced call
    r2 = await app_client.post(
        "/admin/prices", headers=admin_headers,
        json={"provider": "azure", "model": "pl-flow", "input_per_1k": "0.0060",
              "output_per_1k": "0.0120", "effective_from": "2026-05-15T00:00:00+00:00"},
    )
    assert r2.status_code == 201
    assert await _call(app_client, token, "azure/pl-flow") == 200
    costs = await _costs(member)
    assert costs[-1] == second_cost * Decimal(2)
