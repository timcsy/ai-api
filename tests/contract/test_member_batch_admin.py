"""Phase 30 (039): admin member safe-delete + batch delete + batch create.

Contracts in specs/039-member-batch-admin/contracts/member-admin.md.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, AuthAuditLog


async def _new_member(c: AsyncClient, admin: dict, email: str) -> str:
    return (await c.post(
        "/admin/members", headers=admin,
        json={"email": email, "provider": "external", "send_invitation": False},
    )).json()["id"]


async def _alloc(c: AsyncClient, admin: dict, mid: str, model: str = "azure/gpt-4o-mini") -> str:
    return (await c.post(
        "/admin/allocations", headers=admin,
        json={"member_id": mid, "resource_model": model},
    )).json()["id"]


async def _promote(member_id: str) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        from ai_api.models import Member
        m = await s.get(Member, member_id)
        assert m is not None
        m.is_admin = True
        await s.commit()


async def _login_admin(c: AsyncClient, admin: dict, email: str) -> str:
    """Create a local_password admin member, log in (session cookie set on client),
    return the member id."""
    mid = (await c.post(
        "/admin/members", headers=admin,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )).json()["id"]
    await _promote(mid)
    r = await c.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    assert r.status_code == 200
    return mid


# ---------------------------------------------------------------- US1: safe delete

@pytest.mark.asyncio
async def test_safe_delete_member_with_allocation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    mid = await _new_member(app_client, admin_headers, "hasalloc@x.com")
    await _alloc(app_client, admin_headers, mid)
    r = await app_client.delete(f"/admin/members/{mid}", headers=admin_headers)
    assert r.status_code == 204, r.text
    # member gone
    assert (await app_client.get(f"/admin/members/{mid}", headers=admin_headers)).status_code == 404


@pytest.mark.asyncio
async def test_safe_delete_not_found(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.delete("/admin/members/01JNONEXISTENT0000000000000", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_safe_delete_last_admin_blocked(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    mid = await _new_member(app_client, admin_headers, "soleadmin@x.com")
    await _promote(mid)
    r = await app_client.delete(f"/admin/members/{mid}", headers=admin_headers)
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "last_admin"


@pytest.mark.asyncio
async def test_safe_delete_self_blocked(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # session-authed admin deleting self → 403 (guard precedes last-admin)
    own = await _login_admin(app_client, admin_headers, "me@x.com")
    # add a second admin so the failure is attributable to self-guard, not last-admin
    other = await _new_member(app_client, admin_headers, "other@x.com")
    await _promote(other)
    r = await app_client.delete(f"/admin/members/{own}")  # session cookie auth
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "cannot_delete_self"


@pytest.mark.asyncio
async def test_safe_delete_requires_admin(app_client: AsyncClient) -> None:
    r = await app_client.delete("/admin/members/01JANY0000000000000000000000")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------- US2: batch delete

@pytest.mark.asyncio
async def test_bulk_delete_mixed(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _new_member(app_client, admin_headers, "a@x.com")
    b = await _new_member(app_client, admin_headers, "b@x.com")
    await _alloc(app_client, admin_headers, b)  # b has an allocation
    keep = await _new_member(app_client, admin_headers, "keep@x.com")
    r = await app_client.post(
        "/admin/members/bulk-delete", headers=admin_headers,
        json={"member_ids": [a, b, "01JNONEXISTENT0000000000000"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted"] == 2
    assert body["failed"] == 1
    by_id = {x["member_id"]: x for x in body["results"]}
    assert by_id[a]["status"] == "deleted"
    assert by_id[b]["status"] == "deleted"
    assert by_id["01JNONEXISTENT0000000000000"]["status"] == "failed"
    assert by_id["01JNONEXISTENT0000000000000"]["reason"] == "not_found"
    # untouched member still there
    assert (await app_client.get(f"/admin/members/{keep}", headers=admin_headers)).status_code == 200


@pytest.mark.asyncio
async def test_bulk_delete_empty_is_400(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post("/admin/members/bulk-delete", headers=admin_headers, json={"member_ids": []})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bulk_delete_requires_admin(app_client: AsyncClient) -> None:
    r = await app_client.post("/admin/members/bulk-delete", json={"member_ids": ["x"]})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------- US3: batch create

@pytest.mark.asyncio
async def test_bulk_create_mixed(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # pre-existing member
    await _new_member(app_client, admin_headers, "exists@x.com")
    emails = "new1@x.com\nexists@x.com\nbad-email\nnew1@x.com\n"
    r = await app_client.post(
        "/admin/members/bulk-create", headers=admin_headers, json={"emails": emails}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1
    assert body["exists"] == 1
    assert body["invalid"] == 1
    assert body["duplicate"] == 1
    res = body["results"]
    # new1 appears twice: first created (with invitation), second duplicate
    new1 = [x for x in res if x["email"] == "new1@x.com"]
    statuses = {x["status"] for x in new1}
    assert statuses == {"created", "duplicate"}
    created_entry = next(x for x in new1 if x["status"] == "created")
    assert created_entry["invitation_url"]
    assert next(x for x in res if x["email"] == "exists@x.com")["status"] == "exists"
    assert next(x for x in res if x["email"] == "bad-email")["status"] == "invalid"
    # the new member exists + is local_password
    listed = (await app_client.get("/admin/members", headers=admin_headers)).json()
    emails_now = {m["email"] for m in (listed if isinstance(listed, list) else listed["items"])}
    assert "new1@x.com" in emails_now


@pytest.mark.asyncio
async def test_bulk_create_audit(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await app_client.post(
        "/admin/members/bulk-create", headers=admin_headers, json={"emails": "audit1@x.com"}
    )
    sm = get_sessionmaker()
    async with sm() as s:
        from ai_api.models import Member
        m = (await s.execute(select(Member).where(Member.email == "audit1@x.com"))).scalar_one()
        evt = (await s.execute(
            select(AuthAuditLog).where(
                AuthAuditLog.event_type == AuditEventType.member_created,
                AuthAuditLog.target_id == m.id,
            )
        )).scalar_one_or_none()
        assert evt is not None


@pytest.mark.asyncio
async def test_bulk_create_empty_is_400(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post("/admin/members/bulk-create", headers=admin_headers, json={"emails": "  \n \n"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bulk_create_requires_admin(app_client: AsyncClient) -> None:
    r = await app_client.post("/admin/members/bulk-create", json={"emails": "x@x.com"})
    assert r.status_code in (401, 403)
