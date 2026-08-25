"""Batch member ops + tags-in-list (systematic account management: filter+batch).

New bulk endpoints: /admin/members/bulk-status, /bulk-tags, /bulk-allocate; the
member list carries `tags` so the admin UI can filter/show by tag.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _new_member(c: AsyncClient, admin: dict, email: str) -> str:
    r = await c.post(
        "/admin/members", headers=admin,
        json={"email": email, "provider": "external", "send_invitation": False},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _promote(member_id: str) -> None:
    from ai_api.db import get_sessionmaker
    from ai_api.models import Member
    async with get_sessionmaker()() as s:
        m = await s.get(Member, member_id)
        assert m is not None
        m.is_admin = True
        await s.commit()


async def _members(c: AsyncClient, admin: dict) -> dict[str, dict]:
    rows = (await c.get("/admin/members", headers=admin)).json()
    return {m["id"]: m for m in rows}


# ---------------------------------------------------------------- tags in list

@pytest.mark.asyncio
async def test_list_members_includes_tags(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _new_member(app_client, admin_headers, "tagged@x.com")
    r = await app_client.post(
        "/admin/members/bulk-tags", headers=admin_headers,
        json={"member_ids": [mid], "add": ["class-a"]},
    )
    assert r.status_code == 200, r.text
    members = await _members(app_client, admin_headers)
    assert members[mid]["tags"] == ["class-a"]


# ---------------------------------------------------------------- bulk status

@pytest.mark.asyncio
async def test_bulk_status_enable_disable(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _new_member(app_client, admin_headers, "s-a@x.com")
    b = await _new_member(app_client, admin_headers, "s-b@x.com")
    r = await app_client.post(
        "/admin/members/bulk-status", headers=admin_headers,
        json={"member_ids": [a, b], "status": "disabled"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["changed"] == 2
    members = await _members(app_client, admin_headers)
    assert members[a]["status"] == "disabled" and members[b]["status"] == "disabled"

    r2 = await app_client.post(
        "/admin/members/bulk-status", headers=admin_headers,
        json={"member_ids": [a, b], "status": "active"},
    )
    assert r2.json()["changed"] == 2
    members = await _members(app_client, admin_headers)
    assert members[a]["status"] == "active" and members[b]["status"] == "active"


@pytest.mark.asyncio
async def test_bulk_status_last_admin_blocked(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    mid = await _new_member(app_client, admin_headers, "soleadmin@x.com")
    await _promote(mid)  # now the only active admin member
    r = await app_client.post(
        "/admin/members/bulk-status", headers=admin_headers,
        json={"member_ids": [mid], "status": "disabled"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["failed"] == 1 and body["results"][0]["reason"] == "last_admin"
    members = await _members(app_client, admin_headers)
    assert members[mid]["status"] == "active"  # not disabled


# ---------------------------------------------------------------- bulk tags

@pytest.mark.asyncio
async def test_bulk_tags_add_then_remove(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _new_member(app_client, admin_headers, "t-a@x.com")
    b = await _new_member(app_client, admin_headers, "t-b@x.com")
    add = await app_client.post(
        "/admin/members/bulk-tags", headers=admin_headers,
        json={"member_ids": [a, b], "add": ["grade-3", "cohort-x"]},
    )
    assert add.json()["changed"] == 2
    members = await _members(app_client, admin_headers)
    assert set(members[a]["tags"]) == {"cohort-x", "grade-3"}

    rm = await app_client.post(
        "/admin/members/bulk-tags", headers=admin_headers,
        json={"member_ids": [a, b], "remove": ["grade-3"]},
    )
    assert rm.json()["changed"] == 2
    members = await _members(app_client, admin_headers)
    assert members[a]["tags"] == ["cohort-x"]


@pytest.mark.asyncio
async def test_bulk_tags_requires_add_or_remove(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _new_member(app_client, admin_headers, "t-empty@x.com")
    r = await app_client.post(
        "/admin/members/bulk-tags", headers=admin_headers,
        json={"member_ids": [a]},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------- bulk allocate

@pytest.mark.asyncio
async def test_bulk_allocate_grants_then_skips(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = await _new_member(app_client, admin_headers, "al-a@x.com")
    b = await _new_member(app_client, admin_headers, "al-b@x.com")
    r = await app_client.post(
        "/admin/members/bulk-allocate", headers=admin_headers,
        json={"member_ids": [a, b], "resource_model": "azure/gpt-4o-mini",
              "quota_tokens_per_month": 1000000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["granted"] == 2 and r.json()["skipped"] == 0
    # each member now has an allocation for the model
    ma = (await app_client.get(f"/admin/members/{a}", headers=admin_headers)).status_code
    assert ma == 200

    # repeat → skipped (already has active allocation)
    again = await app_client.post(
        "/admin/members/bulk-allocate", headers=admin_headers,
        json={"member_ids": [a, b], "resource_model": "azure/gpt-4o-mini"},
    )
    assert again.json()["granted"] == 0 and again.json()["skipped"] == 2


# ---------------------------------------------------------------- authz

@pytest.mark.asyncio
async def test_bulk_endpoints_require_admin(app_client: AsyncClient) -> None:
    for path in ("bulk-status", "bulk-tags", "bulk-allocate"):
        r = await app_client.post(f"/admin/members/{path}", json={"member_ids": ["x"]})
        assert r.status_code in (401, 403), f"{path}: {r.status_code}"
