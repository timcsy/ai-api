"""US1 integration: aggregate_usage produces correct sums across group_by."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
)


async def _seed(member_email: str, model: str, calls: int, tokens_each: int) -> str:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        m = Member(
            id=str(ULID()),
            email=member_email,
            provider=MemberProvider.external,
            display_name=member_email,
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
            subject_snapshot=member_email,
            resource_model=model,
            status=AllocationStatus.active,
            created_at=now,
            revoked_at=None,
            created_by="test",
            note=None,
            quota_tokens_per_month=None,
            is_service_allocation=False,
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
                    request_id=f"r-{i}",
                    allocation_id=a.id,
                    subject=member_email,
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
        return a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_group_by_member(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed("alice@x.com", "gpt-4o-mini", calls=5, tokens_each=10)
    await _seed("bob@x.com", "gpt-4o-mini", calls=3, tokens_each=20)
    now = datetime.now(UTC)
    from urllib.parse import quote
    from_ = quote((now - timedelta(hours=2)).isoformat())
    to = quote((now + timedelta(hours=1)).isoformat())
    r = await app_client.get(
        f"/admin/usage?group_by=member&from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200
    items = {it["display_name"]: it for it in r.json()["items"]}
    assert items["alice@x.com"]["total_tokens"] == 50
    assert items["alice@x.com"]["call_count"] == 5
    assert items["bob@x.com"]["total_tokens"] == 60
    assert items["bob@x.com"]["call_count"] == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_group_by_model(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed("c1@x.com", "gpt-4o-mini", calls=2, tokens_each=100)
    await _seed("c2@x.com", "gpt-4o", calls=1, tokens_each=50)
    now = datetime.now(UTC)
    from urllib.parse import quote
    from_ = quote((now - timedelta(hours=2)).isoformat())
    to = quote((now + timedelta(hours=1)).isoformat())
    r = await app_client.get(
        f"/admin/usage?group_by=model&from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200
    items = {it["group_key"]: it for it in r.json()["items"]}
    assert items["gpt-4o-mini"]["total_tokens"] == 200
    assert items["gpt-4o"]["total_tokens"] == 50
