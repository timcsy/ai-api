"""Contract test: last-admin guard (Phase 3b.2 FR-006)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog, Member


@pytest.mark.asyncio
async def test_demoting_only_admin_returns_409(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Create and promote alice as the only admin
    alice = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={"email": "alice@x.com", "provider": "external", "send_invitation": False},
        )
    ).json()
    await app_client.patch(
        f"/admin/members/{alice['id']}",
        headers=admin_headers,
        json={"is_admin": True},
    )

    # Attempt to demote — should 409
    r = await app_client.patch(
        f"/admin/members/{alice['id']}",
        headers=admin_headers,
        json={"is_admin": False},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "last_admin_cannot_demote"

    # Verify alice still is_admin=true
    sm = get_sessionmaker()
    async with sm() as s:
        m = await s.get(Member, alice["id"])
        assert m and m.is_admin is True

    # And no demote audit event was written
    async with sm() as s:
        evt = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.member_demoted,
                    AuthAuditLog.target_id == alice["id"],
                )
            )
        ).scalar_one_or_none()
    assert evt is None


@pytest.mark.asyncio
async def test_demoting_with_other_admins_allowed(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    for email in ("a1@x.com", "a2@x.com"):
        m = (
            await app_client.post(
                "/admin/members",
                headers=admin_headers,
                json={"email": email, "provider": "external", "send_invitation": False},
            )
        ).json()
        await app_client.patch(
            f"/admin/members/{m['id']}", headers=admin_headers, json={"is_admin": True}
        )
    # Demote one — must succeed
    m1 = (await app_client.get("/admin/members?email=a1@x.com", headers=admin_headers)).json()[0]
    r = await app_client.patch(
        f"/admin/members/{m1['id']}", headers=admin_headers, json={"is_admin": False}
    )
    assert r.status_code == 200
