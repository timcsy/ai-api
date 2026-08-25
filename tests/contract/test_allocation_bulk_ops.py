"""Batch allocation ops: /admin/allocations/bulk-action + /bulk-quota.

Mirrors the member bulk pattern — per-item independent, reports per-item outcome.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _member(c: AsyncClient, admin: dict, email: str) -> str:
    r = await c.post(
        "/admin/members", headers=admin,
        json={"email": email, "provider": "external", "send_invitation": False},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _alloc(c: AsyncClient, admin: dict, mid: str, model: str = "azure/gpt-4o-mini") -> str:
    r = await c.post(
        "/admin/allocations", headers=admin,
        json={"member_id": mid, "resource_model": model},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _status(c: AsyncClient, admin: dict, aid: str) -> str:
    # The admin list returns all statuses (incl. revoked); frontend filters client-side.
    rows = (await c.get("/admin/allocations", headers=admin)).json()
    for a in rows:
        if a["id"] == aid:
            return a["status"]
    return "missing"


@pytest.mark.asyncio
async def test_bulk_action_pause_resume(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    m = await _member(app_client, admin_headers, "ba-1@x.com")
    a1 = await _alloc(app_client, admin_headers, m, "azure/gpt-4o-mini")
    a2 = await _alloc(app_client, admin_headers, m, "azure/gpt-4o")

    r = await app_client.post(
        "/admin/allocations/bulk-action", headers=admin_headers,
        json={"allocation_ids": [a1, a2], "action": "pause"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["changed"] == 2
    assert await _status(app_client, admin_headers, a1) == "paused"

    r2 = await app_client.post(
        "/admin/allocations/bulk-action", headers=admin_headers,
        json={"allocation_ids": [a1, a2], "action": "resume"},
    )
    assert r2.json()["changed"] == 2
    assert await _status(app_client, admin_headers, a1) == "active"


@pytest.mark.asyncio
async def test_bulk_action_revoke(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    m = await _member(app_client, admin_headers, "ba-2@x.com")
    a1 = await _alloc(app_client, admin_headers, m)
    r = await app_client.post(
        "/admin/allocations/bulk-action", headers=admin_headers,
        json={"allocation_ids": [a1], "action": "revoke"},
    )
    assert r.json()["changed"] == 1
    assert await _status(app_client, admin_headers, a1) == "revoked"


@pytest.mark.asyncio
async def test_bulk_action_unquarantine_skips_non_quarantined(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    m = await _member(app_client, admin_headers, "ba-3@x.com")
    a1 = await _alloc(app_client, admin_headers, m)  # active, not quarantined
    r = await app_client.post(
        "/admin/allocations/bulk-action", headers=admin_headers,
        json={"allocation_ids": [a1], "action": "unquarantine"},
    )
    body = r.json()
    assert body["changed"] == 0 and body["failed"] == 1
    assert body["results"][0]["reason"] == "not_quarantined"


@pytest.mark.asyncio
async def test_bulk_action_invalid_action(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/allocations/bulk-action", headers=admin_headers,
        json={"allocation_ids": ["x"], "action": "explode"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bulk_quota_sets_tokens(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    m = await _member(app_client, admin_headers, "bq-1@x.com")
    a1 = await _alloc(app_client, admin_headers, m, "azure/gpt-4o-mini")
    a2 = await _alloc(app_client, admin_headers, m, "azure/gpt-4o")
    r = await app_client.post(
        "/admin/allocations/bulk-quota", headers=admin_headers,
        json={"allocation_ids": [a1, a2], "quota_tokens_per_month": 5_000_000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["changed"] == 2
    rows = {a["id"]: a for a in (await app_client.get("/admin/allocations", headers=admin_headers)).json()}
    assert rows[a1]["quota_tokens_per_month"] == 5_000_000
    assert rows[a2]["quota_tokens_per_month"] == 5_000_000


@pytest.mark.asyncio
async def test_bulk_quota_requires_a_field(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/allocations/bulk-quota", headers=admin_headers,
        json={"allocation_ids": ["x"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bulk_allocation_endpoints_require_admin(app_client: AsyncClient) -> None:
    for path, body in (
        ("bulk-action", {"allocation_ids": ["x"], "action": "pause"}),
        ("bulk-quota", {"allocation_ids": ["x"], "quota_tokens_per_month": 1}),
    ):
        r = await app_client.post(f"/admin/allocations/{path}", json=body)
        assert r.status_code in (401, 403), f"{path}: {r.status_code}"
