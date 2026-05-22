"""SC-006: after rebalance, the next proxy call uses the new quota immediately."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.config import get_settings
from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rebalance_quota_applied_to_next_proxy_call(
    app_client: AsyncClient, admin_headers, monkeypatch
) -> None:
    monkeypatch.setenv("POOL_TOTAL_TOKENS_PER_MONTH", "1000")
    monkeypatch.setenv("POOL_FLOOR_PER_ALLOCATION", "100")
    get_settings.cache_clear()

    # Create allocation and pre-seed last-month usage so allocation has history
    alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "user@x.com", "resource_model": "gpt-4o-mini"},
        )
    ).json()

    # Seed CURRENT month usage just under the rebalance result quota (1000)
    sm = get_sessionmaker()
    async with sm() as s:
        now = datetime.now(UTC)
        s.add(
            CallRecord(
                id=str(ULID()),
                request_id="seed",
                allocation_id=alloc["id"],
                subject="user@x.com",
                model="gpt-4o-mini",
                started_at=now - timedelta(minutes=1),
                finished_at=now - timedelta(minutes=1),
                status_code=200,
                outcome=CallOutcome.success,
                prompt_tokens=999,
                completion_tokens=0,
                total_tokens=999,
            )
        )
        await s.commit()

    # Manually set a quota that would block the call (< 999)
    await app_client.patch(
        f"/admin/allocations/{alloc['id']}",
        headers=admin_headers,
        json={"quota_tokens_per_month": 500},
    )
    # Call should be blocked
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "quota_exceeded"

    # Rebalance: alone in pool → gets full T (=1000) > 999 → call should succeed
    r2 = await app_client.post(
        "/admin/quota-pool/rebalance", headers=admin_headers
    )
    assert r2.status_code == 200

    stub = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = stub
        r3 = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r3.status_code == 200, r3.json()
