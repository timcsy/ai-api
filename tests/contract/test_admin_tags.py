"""Phase 5 T035 / US3: contract tests for admin tag endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tags_empty(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/tags", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_add_member_tags_creates_and_lists(
    app_client: AsyncClient, admin_headers: dict[str, str], member_id: str
) -> None:
    r = await app_client.post(
        f"/admin/members/{member_id}/tags",
        headers=admin_headers,
        json={"tags": ["eng", "core-team"]},
    )
    assert r.status_code == 200
    assert set(r.json()) == {"eng", "core-team"}

    r2 = await app_client.get(f"/admin/members/{member_id}/tags", headers=admin_headers)
    assert r2.status_code == 200
    assert set(r2.json()) == {"eng", "core-team"}


@pytest.mark.asyncio
async def test_add_invalid_tag_returns_422(
    app_client: AsyncClient, admin_headers: dict[str, str], member_id: str
) -> None:
    r = await app_client.post(
        f"/admin/members/{member_id}/tags",
        headers=admin_headers,
        json={"tags": ["UPPERCASE"]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "invalid_tag"


@pytest.mark.asyncio
async def test_add_to_unknown_member_returns_404(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/members/nonexistent/tags",
        headers=admin_headers,
        json={"tags": ["eng"]},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_remove_member_tag(
    app_client: AsyncClient, admin_headers: dict[str, str], member_id: str
) -> None:
    await app_client.post(
        f"/admin/members/{member_id}/tags",
        headers=admin_headers,
        json={"tags": ["eng", "pm"]},
    )
    r = await app_client.delete(
        f"/admin/members/{member_id}/tags?tag=eng",
        headers=admin_headers,
    )
    assert r.status_code == 204
    r2 = await app_client.get(f"/admin/members/{member_id}/tags", headers=admin_headers)
    assert r2.json() == ["pm"]


@pytest.mark.asyncio
async def test_bulk_apply_idempotent(
    app_client: AsyncClient, admin_headers: dict[str, str], make_member
) -> None:
    m1 = await make_member("a@x.com")
    m2 = await make_member("b@x.com")
    m3 = await make_member("c@x.com")
    # Pre-tag m1
    await app_client.post(
        f"/admin/members/{m1}/tags",
        headers=admin_headers,
        json={"tags": ["eng"]},
    )
    r = await app_client.post(
        "/admin/tags/bulk-apply",
        headers=admin_headers,
        json={"tag": "eng", "member_ids": [m1, m2, m3]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["applied_count"] == 2  # m2 + m3
    assert body["skipped_count"] == 1  # m1 already had it


@pytest.mark.asyncio
async def test_list_tags_after_add_shows_counts(
    app_client: AsyncClient, admin_headers: dict[str, str], make_member
) -> None:
    m1 = await make_member("a@x.com")
    m2 = await make_member("b@x.com")
    await app_client.post(
        f"/admin/members/{m1}/tags",
        headers=admin_headers,
        json={"tags": ["eng"]},
    )
    await app_client.post(
        f"/admin/members/{m2}/tags",
        headers=admin_headers,
        json={"tags": ["eng", "pm"]},
    )
    r = await app_client.get("/admin/tags", headers=admin_headers)
    rows = {row["tag"]: row["member_count"] for row in r.json()}
    assert rows["eng"] == 2
    assert rows["pm"] == 1


@pytest.mark.asyncio
async def test_delete_global_tag(
    app_client: AsyncClient, admin_headers: dict[str, str], member_id: str
) -> None:
    await app_client.post(
        f"/admin/members/{member_id}/tags",
        headers=admin_headers,
        json={"tags": ["eng"]},
    )
    r = await app_client.delete("/admin/tags/eng", headers=admin_headers)
    assert r.status_code == 204
    r2 = await app_client.get("/admin/tags", headers=admin_headers)
    assert r2.json() == []
