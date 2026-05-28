"""Phase 019: admin pause / resume an allocation (reversible, token-preserving).

Contract: specs/019-allocation-pause-resume/contracts/pause-resume.md
Docker-free — contract app_client (in-memory SQLite). Covers the endpoints, the
state machine, and the proxy reject/resume behaviour.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


async def _make_allocation(
    client: AsyncClient, admin_headers: dict[str, str], model: str = "gpt-4o-mini"
) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub_litellm_response() -> dict:
    return {
        "id": "chatcmpl-test", "object": "chat.completion", "created": 0,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


# T005 — pause active → 200, status paused
@pytest.mark.asyncio
async def test_pause_active(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    r = await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"


# T006 — pause keeps token / quota; no reclaim lock
@pytest.mark.asyncio
async def test_pause_preserves_token_and_quota(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    listed = (await app_client.get("/admin/allocations", headers=admin_headers)).json()
    row = next(a for a in listed if a["id"] == alloc["id"])
    assert row["token_prefix"] == alloc["token_prefix"]  # token unchanged
    assert row["quota_tokens_per_month"] == alloc["quota_tokens_per_month"]
    # no reclaim lock created (pause is not revoke)
    locks = (await app_client.get("/admin/self-service-locks", headers=admin_headers)).json()
    assert all(lk.get("model_slug") != alloc["resource_model"] for lk in locks)


# T007 — proxy rejects a paused allocation's calls with allocation_paused
@pytest.mark.asyncio
async def test_proxy_rejects_paused(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "allocation_paused"


# T012 — resume paused → 200, active
@pytest.mark.asyncio
async def test_resume_paused(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    r = await app_client.post(f"/admin/allocations/{alloc['id']}/resume", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"


# T013 — resume → same token works again
@pytest.mark.asyncio
async def test_resume_restores_same_token(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    await app_client.post(f"/admin/allocations/{alloc['id']}/resume", headers=admin_headers)
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub_litellm_response()
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},  # original token
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200, r.text


# T017 — pause non-active → 409, unchanged
@pytest.mark.asyncio
async def test_pause_non_active_rejected(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    # already paused → pause again 409
    await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    r = await app_client.post(f"/admin/allocations/{alloc['id']}/pause", headers=admin_headers)
    assert r.status_code == 409
    # revoked → pause 409
    alloc2 = await _make_allocation(app_client, admin_headers)
    await app_client.delete(f"/admin/allocations/{alloc2['id']}", headers=admin_headers)
    r2 = await app_client.post(f"/admin/allocations/{alloc2['id']}/pause", headers=admin_headers)
    assert r2.status_code == 409


# T018 — resume non-paused → 409
@pytest.mark.asyncio
async def test_resume_non_paused_rejected(app_client: AsyncClient, admin_headers) -> None:
    alloc = await _make_allocation(app_client, admin_headers)  # active, not paused
    r = await app_client.post(f"/admin/allocations/{alloc['id']}/resume", headers=admin_headers)
    assert r.status_code == 409


# T019 — pause/resume unknown id → 404
@pytest.mark.asyncio
async def test_pause_resume_unknown_404(app_client: AsyncClient, admin_headers) -> None:
    rp = await app_client.post("/admin/allocations/01JUNKJUNKJUNKJUNKJUNK0000/pause", headers=admin_headers)
    rr = await app_client.post("/admin/allocations/01JUNKJUNKJUNKJUNKJUNK0000/resume", headers=admin_headers)
    assert rp.status_code == 404
    assert rr.status_code == 404
