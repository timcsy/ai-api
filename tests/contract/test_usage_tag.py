"""Phase 15: contract tests for tag-dimension usage + drill-down + export + isolation.

Contract: specs/023-tag-group-rollup/contracts/admin-usage-tag.openapi.yaml
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

import pytest
from httpx import AsyncClient
from ulid import ULID


async def _seed_tagged_member(email: str, tokens: int, *tags: str) -> str:
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

    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        m = Member(
            id=str(ULID()), email=email, provider=MemberProvider.external,
            display_name=email, status=MemberStatus.active, password_hash=None,
            created_at=now, disabled_at=None, created_by="test",
        )
        s.add(m)
        await s.flush()
        a = Allocation(
            id=str(ULID()), member_id=m.id, subject_snapshot=email,
            resource_model="gpt-4o-mini", status=AllocationStatus.active,
            created_at=now, revoked_at=None, created_by="test", note=None,
            quota_tokens_per_month=None, is_service_allocation=False,
        )
        s.add(a)
        s.add(Credential(
            id=str(ULID()), name="預設",
            allocation_id=a.id, token_fingerprint=str(ULID()) + "x" * 20,
            token_prefix="aiapi_xx", created_at=now,
        ))
        ts = now - timedelta(minutes=5)
        s.add(CallRecord(
            id=str(ULID()), request_id=f"r-{ULID()}", allocation_id=a.id,
            subject=email, model="gpt-4o-mini", started_at=ts, finished_at=ts,
            status_code=200, outcome=CallOutcome.success,
            prompt_tokens=tokens, completion_tokens=0, total_tokens=tokens,
            cost_usd=Decimal("0.001"),
        ))
        for t in tags:
            s.add(MemberTag(
                member_id=m.id, tag=t, added_by="test", added_at=now,
                source=TagSource.manual, rule_id=None,
            ))
        await s.commit()
        return m.id


def _range() -> tuple[str, str]:
    now = datetime.now(UTC)
    return (
        quote((now - timedelta(hours=1)).isoformat()),
        quote((now + timedelta(hours=1)).isoformat()),
    )


# ----- T007 -----

@pytest.mark.asyncio
async def test_usage_group_by_tag_endpoint(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_tagged_member("a@x.com", 1000, "class-101")
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage?group_by=tag&from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["group_by"] == "tag"
    items = {it["group_key"]: it for it in body["items"]}
    assert "class-101" in items
    assert items["class-101"]["total_tokens"] == 1000
    assert items["class-101"]["display_name"] == "class-101"


# ----- T008 -----

@pytest.mark.asyncio
async def test_existing_group_by_unchanged(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_tagged_member("a@x.com", 1000, "class-101")
    from_, to = _range()
    for dim in ("member", "allocation", "model"):
        r = await app_client.get(
            f"/admin/usage?group_by={dim}&from={from_}&to={to}", headers=admin_headers
        )
        assert r.status_code == 200, f"{dim}: {r.text}"
        assert r.json()["group_by"] == dim


# ----- T014 -----

@pytest.mark.asyncio
async def test_tag_members_drilldown(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_tagged_member("a@x.com", 1000, "class-101")
    await _seed_tagged_member("b@x.com", 500, "class-101")
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage/tag/class-101/members?from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tag"] == "class-101"
    members = {m["display_name"]: m for m in body["members"]}
    assert members["a@x.com"]["total_tokens"] == 1000
    assert members["b@x.com"]["total_tokens"] == 500


# ----- T015 -----

@pytest.mark.asyncio
async def test_tag_members_drilldown_empty_tag(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage/tag/nonexistent/members?from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["members"] == []


# ----- T024 -----

@pytest.mark.asyncio
async def test_tag_csv_export(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_tagged_member("a@x.com", 1000, "class-101")
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage.csv?group_by=tag&from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200
    assert "class-101" in r.text


# ----- T025 -----

@pytest.mark.asyncio
async def test_tag_json_export(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_tagged_member("a@x.com", 1000, "class-101")
    from_, to = _range()
    r = await app_client.get(
        f"/admin/usage.json?group_by=tag&from={from_}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200
    rows = {it["group_key"]: it for it in r.json()}
    assert rows["class-101"]["total_tokens"] == 1000


# ----- T029 (isolation) -----

@pytest.mark.asyncio
async def test_tag_endpoints_admin_only(app_client: AsyncClient) -> None:
    from_, to = _range()
    r1 = await app_client.get(f"/admin/usage?group_by=tag&from={from_}&to={to}")
    assert r1.status_code in (401, 403)
    r2 = await app_client.get(f"/admin/usage/tag/class-101/members?from={from_}&to={to}")
    assert r2.status_code in (401, 403)
