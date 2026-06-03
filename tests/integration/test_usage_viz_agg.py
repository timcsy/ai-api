"""Phase 14 US2: heatmap aggregation correctness (weekday x hour, UTC+8)."""
from __future__ import annotations

from datetime import UTC, datetime
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
)


async def _seed_call_at(email: str, tokens: int, when: datetime) -> None:
    """One member+allocation+success call at a specific UTC timestamp."""
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
            allocation_id=a.id, token_fingerprint=str(ULID()) + "x" * 20,
            token_prefix="aiapi_xx", created_at=now,
        ))
        s.add(CallRecord(
            id=str(ULID()), request_id=f"r-{ULID()}", allocation_id=a.id,
            subject=email, model="gpt-4o-mini", started_at=when, finished_at=when,
            status_code=200, outcome=CallOutcome.success,
            prompt_tokens=tokens, completion_tokens=0, total_tokens=tokens,
            cost_usd=Decimal("0.001"),
        ))
        await s.commit()


# ----- T020 -----

@pytest.mark.integration
@pytest.mark.asyncio
async def test_heatmap_buckets_by_weekday_hour_utc8(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # 2026-05-11 04:00 UTC + 8h = 2026-05-11 12:00 (UTC+8). 2026-05-11 is a
    # Monday → weekday=1 (0=Sunday), hour=12. Two calls land in that cell.
    when = datetime(2026, 5, 11, 4, 0, tzinfo=UTC)
    await _seed_call_at("a@x.com", 1000, when)
    await _seed_call_at("b@x.com", 500, when)

    frm = quote(datetime(2026, 5, 1, tzinfo=UTC).isoformat())
    to = quote(datetime(2026, 5, 31, tzinfo=UTC).isoformat())
    r = await app_client.get(
        f"/admin/usage/heatmap?from={frm}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["timezone"] == "UTC+8"
    cells = body["cells"]
    assert len(cells) <= 168
    hit = [c for c in cells if c["weekday"] == 1 and c["hour"] == 12]
    assert len(hit) == 1
    assert hit[0]["tokens"] == 1500
    assert hit[0]["call_count"] == 2


# ----- T021 -----

@pytest.mark.integration
@pytest.mark.asyncio
async def test_heatmap_admin_only(app_client: AsyncClient) -> None:
    frm = quote(datetime(2026, 5, 1, tzinfo=UTC).isoformat())
    to = quote(datetime(2026, 5, 31, tzinfo=UTC).isoformat())
    r = await app_client.get(f"/admin/usage/heatmap?from={frm}&to={to}")
    assert r.status_code in (401, 403)
