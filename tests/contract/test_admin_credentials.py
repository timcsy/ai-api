"""Contract tests: admin per-device credential management (Phase 18, US3).

Admin can list every credential of an allocation and revoke any one of them;
revoking writes an audit record and does not affect the other credentials.
Unauthenticated access is rejected.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog
from ai_api.services.allocations import AllocationService


async def _make_allocation(client: AsyncClient, admin_headers: dict[str, str]) -> str:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "carol@example.com", "resource_model": "gpt-4o-mini"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_second_credential(allocation_id: str, name: str) -> tuple[str, str]:
    """Add a second credential directly via the service. Returns (cred_id, plaintext)."""
    sm = get_sessionmaker()
    async with sm() as s:
        svc = AllocationService(s)
        alloc = await svc.get(allocation_id)
        assert alloc is not None
        cred, token = await svc.add_credential(alloc, name=name)
        await s.commit()
        return cred.id, token.plaintext


@pytest.mark.asyncio
async def test_admin_list_credentials(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id = await _make_allocation(app_client, admin_headers)
    await _seed_second_credential(alloc_id, "carol-laptop")

    r = await app_client.get(
        f"/admin/allocations/{alloc_id}/credentials", headers=admin_headers
    )
    assert r.status_code == 200
    creds = r.json()
    assert len(creds) == 2
    assert {c["name"] for c in creds} == {"預設", "carol-laptop"}
    for c in creds:
        assert "token" not in c


@pytest.mark.asyncio
async def test_admin_revoke_credential_isolated_and_audited(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id = await _make_allocation(app_client, admin_headers)
    cred_id, second_plain = await _seed_second_credential(alloc_id, "carol-laptop")

    r = await app_client.request(
        "DELETE",
        f"/admin/allocations/{alloc_id}/credentials/{cred_id}",
        headers=admin_headers,
    )
    assert r.status_code == 204

    sm = get_sessionmaker()
    async with sm() as s:
        svc = AllocationService(s)
        # The revoked credential no longer resolves; the default one still does.
        assert await svc.lookup_by_token(second_plain) is None
        creds = list(await svc.list_credentials(alloc_id))
        assert len(creds) == 2
        revoked = next(c for c in creds if c.id == cred_id)
        assert revoked.revoked_at is not None
        assert sum(1 for c in creds if c.revoked_at is None) == 1

        # An audit record was written.
        rows = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.credential_revoked,
                    AuthAuditLog.target_id == cred_id,
                )
            )
        ).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_admin_credentials_requires_auth(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/allocations/some-id/credentials")
    assert r.status_code == 401
