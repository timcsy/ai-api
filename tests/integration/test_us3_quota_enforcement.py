"""US3: proxy must reject calls when monthly token usage hits the quota cap."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord


async def _make_alloc(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@x.com", "resource_model": "gpt-4o-mini"},
    )
    return r.json()


async def _seed_usage(allocation_id: str, total_tokens_so_far: int) -> None:
    """Insert a synthetic CallRecord this month with `total_tokens_so_far`."""
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            CallRecord(
                id=str(ULID()),
                request_id="seed",
                allocation_id=allocation_id,
                subject="alice@x.com",
                model="gpt-4o-mini",
                started_at=now - timedelta(minutes=10),
                finished_at=now - timedelta(minutes=10),
                status_code=200,
                outcome=CallOutcome.success,
                prompt_tokens=total_tokens_so_far,
                completion_tokens=0,
                total_tokens=total_tokens_so_far,
                cost_usd=None,
            )
        )
        await s.commit()


def _stub() -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_under_quota_passes(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_alloc(app_client, admin_headers)
    # Set quota and seed usage just under it
    await app_client.patch(
        f"/admin/allocations/{alloc['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": 100},
    )
    await _seed_usage(alloc["id"], 99)
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_at_or_above_quota_rejected(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_alloc(app_client, admin_headers)
    await app_client.patch(
        f"/admin/allocations/{alloc['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": 100},
    )
    await _seed_usage(alloc["id"], 100)  # exactly at cap
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "quota_exceeded"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unlimited_quota_never_blocks(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_alloc(app_client, admin_headers)
    # quota_tokens_per_month default NULL
    await _seed_usage(alloc["id"], 1_000_000)
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200
