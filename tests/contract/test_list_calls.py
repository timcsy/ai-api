"""Contract tests for GET /admin/allocations/{id}/calls."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


def _stub() -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


@pytest.mark.asyncio
async def test_list_calls_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get(
        "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ/calls", headers=admin_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_calls_requires_admin(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "alice", "resource_model": "gpt-4o-mini"},
        )
    ).json()
    r = await app_client.get(f"/admin/allocations/{alloc['id']}/calls")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_calls_includes_success_and_reject(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "alice@example.com", "resource_model": "gpt-4o-mini"},
        )
    ).json()
    token = alloc["token"]

    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ok"}]},
        )

    # And a model-mismatch rejection
    await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "other-model", "messages": [{"role": "user", "content": "no"}]},
    )

    r = await app_client.get(f"/admin/allocations/{alloc['id']}/calls", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    outcomes = {it["outcome"] for it in items}
    assert {"success", "rejected_model_mismatch"} <= outcomes
    success = next(it for it in items if it["outcome"] == "success")
    assert success["prompt_tokens"] == 3
    assert success["total_tokens"] == 8
    assert success["allocation_id"] == alloc["id"]
    assert success["subject"] == "alice@example.com"
