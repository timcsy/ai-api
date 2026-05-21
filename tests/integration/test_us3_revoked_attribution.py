"""Regression: revoked-rejected call must still be attributed to its allocation."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoked_call_record_carries_allocation_id(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "revtest@example.com", "resource_model": "gpt-4o-mini"},
        )
    ).json()
    token = alloc["token"]

    # Revoke
    rv = await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
    assert rv.status_code == 200

    # Call after revoke — should be rejected as allocation_revoked
    resp = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "allocation_revoked"

    # The reject record must appear in the allocation's call list (not null/anonymous).
    listing = await app_client.get(
        f"/admin/allocations/{alloc['id']}/calls", headers=admin_headers
    )
    assert listing.status_code == 200
    records = listing.json()
    revoked_records = [r for r in records if r["outcome"] == "rejected_revoked"]
    assert len(revoked_records) == 1
    assert revoked_records[0]["allocation_id"] == alloc["id"]
    assert revoked_records[0]["subject"] == "revtest@example.com"
