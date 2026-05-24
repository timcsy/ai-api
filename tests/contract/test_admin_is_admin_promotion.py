"""Contract tests for PATCH /admin/members + is_admin field (Phase 3b.2)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog


@pytest.mark.asyncio
async def test_promote_via_patch_sets_is_admin(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    member = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={
                "email": "alice@x.com",
                "provider": "local_password",
                "initial_password": "VerySafePass123",
                "send_invitation": False,
            },
        )
    ).json()
    assert member["is_admin"] is False

    r = await app_client.patch(
        f"/admin/members/{member['id']}",
        headers=admin_headers,
        json={"is_admin": True},
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


@pytest.mark.asyncio
async def test_promote_emits_audit_event(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    member = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={
                "email": "bob@x.com",
                "provider": "external",
                "send_invitation": False,
            },
        )
    ).json()
    await app_client.patch(
        f"/admin/members/{member['id']}",
        headers=admin_headers,
        json={"is_admin": True},
    )
    sm = get_sessionmaker()
    async with sm() as s:
        evt = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.member_promoted,
                    AuthAuditLog.target_id == member["id"],
                )
            )
        ).scalar_one_or_none()
    assert evt is not None


@pytest.mark.asyncio
async def test_demote_emits_audit_event(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Build two admins so demotion is allowed
    for email in ("a1@x.com", "a2@x.com"):
        m = (
            await app_client.post(
                "/admin/members",
                headers=admin_headers,
                json={
                    "email": email,
                    "provider": "external",
                    "send_invitation": False,
                },
            )
        ).json()
        await app_client.patch(
            f"/admin/members/{m['id']}",
            headers=admin_headers,
            json={"is_admin": True},
        )

    # Demote a1
    m1 = (await app_client.get("/admin/members?email=a1@x.com", headers=admin_headers)).json()[0]
    r = await app_client.patch(
        f"/admin/members/{m1['id']}",
        headers=admin_headers,
        json={"is_admin": False},
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is False

    sm = get_sessionmaker()
    async with sm() as s:
        evt = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.member_demoted,
                    AuthAuditLog.target_id == m1["id"],
                )
            )
        ).scalar_one_or_none()
    assert evt is not None


@pytest.mark.asyncio
async def test_me_response_includes_is_admin(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    member = (
        await app_client.post(
            "/admin/members",
            headers=admin_headers,
            json={
                "email": "dave@x.com",
                "provider": "local_password",
                "initial_password": "VerySafePass123",
                "send_invitation": False,
            },
        )
    ).json()
    await app_client.patch(
        f"/admin/members/{member['id']}",
        headers=admin_headers,
        json={"is_admin": True},
    )
    await app_client.post(
        "/auth/local/login", json={"email": "dave@x.com", "password": "VerySafePass123"}
    )
    me = await app_client.get("/me")
    assert me.status_code == 200
    assert me.json()["is_admin"] is True
