"""Phase 17: /me/usage/timeseries is strictly scoped to the logged-in member.

The hard rule (spec FR-002): member A's timeseries must NEVER include member B's
calls, and there is no parameter to view another member. Postgres-backed.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import (
    Allocation,
    AllocationOrigin,
    AllocationStatus,
    CallOutcome,
    CallRecord,
)

DAY = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)


async def _create_member(client: AsyncClient, admin_headers: dict[str, str], email: str) -> str:
    r = await client.post(
        "/admin/members",
        headers=admin_headers,
        json={"email": email, "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _seed(member_id: str, model: str, total: int) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        alloc_id = str(ULID())
        s.add(Allocation(
            id=alloc_id, member_id=member_id, subject_snapshot=model,
            resource_model=model, status=AllocationStatus.active, created_at=DAY,
            revoked_at=None, created_by="test", note=None, quota_tokens_per_month=None,
            is_service_allocation=False, quota_locked=False, origin=AllocationOrigin.admin,
        ))
        s.add(CallRecord(
            id=str(ULID()), request_id=str(ULID()), allocation_id=alloc_id,
            subject=model, model=model, started_at=DAY, finished_at=DAY,
            status_code=200, outcome=CallOutcome.success,
            prompt_tokens=total // 2, completion_tokens=total - total // 2,
            total_tokens=total, cost_usd=0.01, error_message=None,
        ))
        await s.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_timeseries_excludes_other_member(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    a = await _create_member(app_client, admin_headers, "a-iso@x.com")
    b = await _create_member(app_client, admin_headers, "b-iso@x.com")
    await _seed(a, "azure/m", 1000)  # A's usage
    await _seed(b, "azure/m", 9999)  # B's usage — must NOT leak to A

    # log in as A (session cookie); range covers DAY
    await app_client.post(
        "/auth/local/login", json={"email": "a-iso@x.com", "password": "VerySafePass123"}
    )
    r = await app_client.get(
        "/me/usage/timeseries",
        params={"from": "2026-05-01T00:00:00+00:00", "to": "2026-05-31T00:00:00+00:00"},
    )
    assert r.status_code == 200, r.text
    total = sum(p["tokens"] for p in r.json()["points"])
    assert total == 1000  # only A's usage; B's 9999 excluded
