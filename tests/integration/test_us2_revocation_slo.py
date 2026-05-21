"""US2 SLO test: revoke then call within 5s must be rejected."""
from __future__ import annotations

import time
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
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoke_then_call_rejected_within_slo(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "bob@example.com", "resource_model": "gpt-4o-mini"},
        )
    ).aclose() or None  # placate type checkers
    create_resp = await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "bob@example.com", "resource_model": "gpt-4o-mini"},
    )
    alloc = create_resp.json()
    token = alloc["token"]

    # Sanity: works before revoke
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        ok = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert ok.status_code == 200

    # Revoke
    revoke_at = time.monotonic()
    rv = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    assert rv.status_code == 200

    # Call again — must be rejected; wall-clock check against SLO
    resp = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    elapsed = time.monotonic() - revoke_at
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "allocation_revoked"
    assert elapsed <= 5.0, f"revocation took {elapsed:.2f}s, exceeds SLO 5s"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoke_a_does_not_affect_b(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    def make_payload(subject: str) -> dict:
        return {"subject": subject, "resource_model": "gpt-4o-mini"}

    a = (await app_client.post("/admin/allocations", headers=admin_headers, json=make_payload("a@x"))).json()
    b = (await app_client.post("/admin/allocations", headers=admin_headers, json=make_payload("b@x"))).json()

    rv = await app_client.delete(f"/admin/allocations/{a['id']}", headers=admin_headers)
    assert rv.status_code == 200

    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        resp_a = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {a['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
        resp_b = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {b['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert resp_a.status_code == 403
    assert resp_b.status_code == 200
