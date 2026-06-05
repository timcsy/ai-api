"""Phase 15 US1/US2: tag-dimension aggregation correctness + overlap."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import (
    Allocation,
    AllocationStatus,
    CallOutcome,
    CallRecord,
    Credential,
    Member,
    MemberProvider,
    MemberStatus,
    MemberTag,
    TagSource,
)


async def _seed_member(
    email: str, model: str, calls: int, tokens_each: int, *, service: bool = False
) -> str:
    """Create a member + allocation + N success call records. Returns member_id."""
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        m = Member(
            id=str(ULID()),
            email=email,
            provider=MemberProvider.external,
            display_name=email,
            status=MemberStatus.active,
            password_hash=None,
            created_at=now,
            disabled_at=None,
            created_by="test",
        )
        s.add(m)
        await s.flush()
        a = Allocation(
            id=str(ULID()),
            member_id=m.id,
            subject_snapshot=email,
            resource_model=model,
            status=AllocationStatus.active,
            created_at=now,
            revoked_at=None,
            created_by="test",
            note=None,
            quota_tokens_per_month=None,
            is_service_allocation=service,
        )
        s.add(a)
        await s.flush()
        s.add(
            Credential(
                id=str(ULID()),
                name="預設",
                member_id=a.member_id,
                token_fingerprint=str(ULID()) + "xxxxxxxxxxxxxxxxxxxx",
                token_prefix="aiapi_xx",
                created_at=now,
            )
        )
        for i in range(calls):
            ts = now - timedelta(hours=1) + timedelta(seconds=i)
            s.add(
                CallRecord(
                    id=str(ULID()),
                    request_id=f"r-{ULID()}",
                    allocation_id=a.id,
                    subject=email,
                    model=model,
                    started_at=ts,
                    finished_at=ts,
                    status_code=200,
                    outcome=CallOutcome.success,
                    prompt_tokens=tokens_each,
                    completion_tokens=0,
                    total_tokens=tokens_each,
                    cost_usd=Decimal("0.001"),
                )
            )
        await s.commit()
        return m.id


async def _add_call_at(member_id: str, model: str, tokens: int, when: datetime) -> None:
    """Add a single call record to a member's (first) allocation at a given time."""
    from sqlalchemy import select

    sm = get_sessionmaker()
    async with sm() as s:
        alloc = (
            await s.execute(select(Allocation).where(Allocation.member_id == member_id))
        ).scalars().first()
        assert alloc is not None
        s.add(
            CallRecord(
                id=str(ULID()),
                request_id=f"r-{ULID()}",
                allocation_id=alloc.id,
                subject="x",
                model=model,
                started_at=when,
                finished_at=when,
                status_code=200,
                outcome=CallOutcome.success,
                prompt_tokens=tokens,
                completion_tokens=0,
                total_tokens=tokens,
                cost_usd=Decimal("0.001"),
            )
        )
        await s.commit()


async def _tag(member_id: str, *tags: str) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        for t in tags:
            s.add(
                MemberTag(
                    member_id=member_id,
                    tag=t,
                    added_by="test",
                    added_at=now,
                    source=TagSource.manual,
                    rule_id=None,
                )
            )
        await s.commit()


def _range() -> tuple[str, str]:
    now = datetime.now(UTC)
    return (
        quote((now - timedelta(hours=2)).isoformat()),
        quote((now + timedelta(hours=1)).isoformat()),
    )


# ----- T003 -----

@pytest.mark.integration
@pytest.mark.asyncio
async def test_tag_aggregation_equals_member_sum(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    a = await _seed_member("a@x.com", "gpt-4o-mini", calls=5, tokens_each=200)  # 1000
    b = await _seed_member("b@x.com", "gpt-4o-mini", calls=5, tokens_each=100)  # 500
    await _tag(a, "class-101")
    await _tag(b, "class-101")
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage?group_by=tag&from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["group_by"] == "tag"
    items = {it["group_key"]: it for it in r.json()["items"]}
    assert items["class-101"]["total_tokens"] == 1500  # 1000 + 500
    assert items["class-101"]["call_count"] == 10


# ----- T004 -----

@pytest.mark.integration
@pytest.mark.asyncio
async def test_tag_respects_time_range(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    a = await _seed_member("a@x.com", "gpt-4o-mini", calls=5, tokens_each=200)  # 1000 in-range
    await _tag(a, "class-101")
    # Add an out-of-range call (10 hours ago)
    await _add_call_at(a, "gpt-4o-mini", 9999, datetime.now(UTC) - timedelta(hours=10))
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage?group_by=tag&from={from_}&to={to}", headers=admin_headers
    )
    items = {it["group_key"]: it for it in r.json()["items"]}
    assert items["class-101"]["total_tokens"] == 1000  # out-of-range 9999 excluded


# ----- T005 -----

@pytest.mark.integration
@pytest.mark.asyncio
async def test_tag_service_only_filter(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    svc = await _seed_member("svc@x.com", "gpt-4o-mini", calls=2, tokens_each=100, service=True)
    nonsvc = await _seed_member("u@x.com", "gpt-4o-mini", calls=2, tokens_each=100, service=False)
    await _tag(svc, "bots")
    await _tag(nonsvc, "bots")
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage?group_by=tag&service_only=true&from={from_}&to={to}",
        headers=admin_headers,
    )
    items = {it["group_key"]: it for it in r.json()["items"]}
    assert items["bots"]["total_tokens"] == 200  # only the service allocation's 2*100


# ----- T013 (US2 overlap, placed with the integration suite) -----

@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_tag_member_counts_in_each(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    c = await _seed_member("c@x.com", "gpt-4o-mini", calls=3, tokens_each=100)  # 300
    await _tag(c, "class-101", "資訊社")  # member in TWO tags
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage?group_by=tag&from={from_}&to={to}", headers=admin_headers
    )
    items = {it["group_key"]: it for it in r.json()["items"]}
    # C's 300 counts in BOTH tags (intended overlap)
    assert items["class-101"]["total_tokens"] == 300
    assert items["資訊社"]["total_tokens"] == 300
