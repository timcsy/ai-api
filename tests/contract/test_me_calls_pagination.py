"""Contract tests for /me/allocations/{id}/calls cursor pagination (Phase 3b.1 FR-001)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord


async def _make_member_login_and_alloc(
    client: AsyncClient, admin_headers: dict[str, str]
) -> dict:
    """Create local member, log in, create an allocation, return allocation dict."""
    await client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": "alice@x.com",
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    await client.post(
        "/auth/local/login", json={"email": "alice@x.com", "password": "VerySafePass123"}
    )
    me = (await client.get("/me")).json()
    alloc = (
        await client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    return alloc


async def _seed_calls(allocation_id: str, n: int) -> list[str]:
    """Seed n CallRecord rows. Returns the ids in order of insertion."""
    sm = get_sessionmaker()
    base = datetime.now(UTC) - timedelta(hours=n)
    ids: list[str] = []
    async with sm() as s:
        for i in range(n):
            ulid = str(ULID())
            ids.append(ulid)
            s.add(
                CallRecord(
                    id=ulid,
                    request_id=f"r-{i}",
                    allocation_id=allocation_id,
                    subject="alice@x.com",
                    model="gpt-4o-mini",
                    started_at=base + timedelta(minutes=i),
                    finished_at=base + timedelta(minutes=i),
                    status_code=200,
                    outcome=CallOutcome.success,
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                )
            )
        await s.commit()
    return ids


@pytest.mark.asyncio
async def test_calls_returns_dict_with_items_and_next_cursor(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_member_login_and_alloc(app_client, admin_headers)
    await _seed_calls(alloc["id"], n=5)

    r = await app_client.get(f"/me/allocations/{alloc['id']}/calls")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "items" in body
    assert "next_before_id" in body
    assert len(body["items"]) == 5
    # All 5 returned in one page → no more
    assert body["next_before_id"] is None


@pytest.mark.asyncio
async def test_calls_limit_and_cursor_paginate(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_member_login_and_alloc(app_client, admin_headers)
    await _seed_calls(alloc["id"], n=30)

    # Page 1: first 20
    r1 = await app_client.get(f"/me/allocations/{alloc['id']}/calls?limit=20")
    page1 = r1.json()
    assert len(page1["items"]) == 20
    assert page1["next_before_id"] is not None

    # Page 2: next 10 via cursor
    r2 = await app_client.get(
        f"/me/allocations/{alloc['id']}/calls?limit=20&before_id={page1['next_before_id']}"
    )
    page2 = r2.json()
    assert len(page2["items"]) == 10
    assert page2["next_before_id"] is None  # no more


@pytest.mark.asyncio
async def test_calls_default_limit_is_20(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_member_login_and_alloc(app_client, admin_headers)
    await _seed_calls(alloc["id"], n=25)
    r = await app_client.get(f"/me/allocations/{alloc['id']}/calls")
    body = r.json()
    assert len(body["items"]) == 20
    assert body["next_before_id"] is not None


async def _seed_calls_id_desc_started_asc(allocation_id: str, n: int) -> None:
    """Seed n rows where the ULID `id` order is the REVERSE of started_at order,
    all within the same wall-clock instant.

    Regression for the keyset-cursor bug: the query sorts by (started_at, id) but
    the old cursor filtered on `id` alone. When ids don't track started_at (exactly
    what happens with same-millisecond ULIDs), an `id < before` boundary returns a
    non-deterministic page size. Here we force the worst case deterministically.
    """
    sm = get_sessionmaker()
    instant = datetime.now(UTC)
    # Descending ULIDs (lexically) paired with ascending started_at → the two
    # orderings are exact opposites, so an id-only cursor is guaranteed wrong.
    ids = sorted((str(ULID()) for _ in range(n)), reverse=True)
    async with sm() as s:
        for i, ulid in enumerate(ids):
            s.add(
                CallRecord(
                    id=ulid,
                    request_id=f"r-{i}",
                    allocation_id=allocation_id,
                    subject="alice@x.com",
                    model="gpt-4o-mini",
                    started_at=instant + timedelta(minutes=i),
                    finished_at=instant + timedelta(minutes=i),
                    status_code=200,
                    outcome=CallOutcome.success,
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                )
            )
        await s.commit()


@pytest.mark.asyncio
async def test_calls_cursor_paginates_when_id_order_differs_from_time(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_member_login_and_alloc(app_client, admin_headers)
    await _seed_calls_id_desc_started_asc(alloc["id"], n=30)

    r1 = await app_client.get(f"/me/allocations/{alloc['id']}/calls?limit=20")
    page1 = r1.json()
    assert len(page1["items"]) == 20
    assert page1["next_before_id"] is not None

    r2 = await app_client.get(
        f"/me/allocations/{alloc['id']}/calls?limit=20&before_id={page1['next_before_id']}"
    )
    page2 = r2.json()
    assert len(page2["items"]) == 10  # exactly the remainder — no off-by-N
    assert page2["next_before_id"] is None
    # No overlap between pages (each call returned once).
    ids1 = {it["id"] for it in page1["items"]}
    ids2 = {it["id"] for it in page2["items"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_calls_limit_validation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_member_login_and_alloc(app_client, admin_headers)
    r = await app_client.get(f"/me/allocations/{alloc['id']}/calls?limit=0")
    assert r.status_code == 422
    r = await app_client.get(f"/me/allocations/{alloc['id']}/calls?limit=101")
    assert r.status_code == 422
