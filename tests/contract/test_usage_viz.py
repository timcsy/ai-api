"""Phase 14: contract tests for admin visualization endpoints.

Contract: specs/024-admin-visualization/contracts/admin-viz.openapi.yaml
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

import pytest
from httpx import AsyncClient
from ulid import ULID


async def _seed_call(
    *, email: str, tokens: int, cost: str, started_at: datetime, model: str = "gpt-4o-mini"
) -> str:
    """Seed one member+allocation+success CallRecord at a given timestamp.

    Each call gets its own allocation so platform-wide aggregation has to sum
    across multiple allocations. Returns the allocation id.
    """
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
            resource_model=model, status=AllocationStatus.active,
            created_at=now, revoked_at=None, created_by="test", note=None,
            quota_tokens_per_month=None, is_service_allocation=False,
        )
        s.add(a)
        s.add(Credential(
            id=str(ULID()), name="預設",
            allocation_id=a.id, token_fingerprint=str(ULID()) + "x" * 20,
            token_prefix="aiapi_xx", created_at=now,
        ))
        s.add(CallRecord(
            id=str(ULID()), request_id=f"r-{ULID()}", allocation_id=a.id,
            subject=email, model=model, started_at=started_at, finished_at=started_at,
            status_code=200, outcome=CallOutcome.success,
            prompt_tokens=tokens, completion_tokens=0, total_tokens=tokens,
            cost_usd=Decimal(cost),
        ))
        await s.commit()
        return a.id


async def _seed_catalog(slug: str, provider: str) -> None:
    from ai_api.db import get_sessionmaker
    from ai_api.models import ModelCatalog

    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=provider, display_name=slug, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=[], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()


# ----- T006 -----

@pytest.mark.asyncio
async def test_platform_timeseries_sums_all_allocations(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Two allocations, same day → that day's point sums both.
    day1 = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
    day2 = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
    await _seed_call(email="a@x.com", tokens=1000, cost="0.10", started_at=day1)
    await _seed_call(email="b@x.com", tokens=500, cost="0.05", started_at=day1)
    await _seed_call(email="c@x.com", tokens=300, cost="0.03", started_at=day2)

    frm = quote(datetime(2026, 5, 1, tzinfo=UTC).isoformat())
    to = quote(datetime(2026, 5, 31, tzinfo=UTC).isoformat())
    r = await app_client.get(
        f"/admin/usage/timeseries?bucket=day&from={frm}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bucket"] == "day"
    points = {p["ts"][:10]: p for p in body["points"]}
    assert points["2026-05-10"]["tokens"] == 1500
    assert points["2026-05-10"]["call_count"] == 2
    assert points["2026-05-11"]["tokens"] == 300
    assert points["2026-05-11"]["call_count"] == 1


# ----- T007 -----

@pytest.mark.asyncio
async def test_platform_timeseries_admin_only(app_client: AsyncClient) -> None:
    frm = quote(datetime(2026, 5, 1, tzinfo=UTC).isoformat())
    to = quote(datetime(2026, 5, 31, tzinfo=UTC).isoformat())
    r = await app_client.get(f"/admin/usage/timeseries?bucket=day&from={frm}&to={to}")
    assert r.status_code in (401, 403)


# ----- T008 -----

@pytest.mark.asyncio
async def test_platform_timeseries_invalid_range(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    now = datetime.now(UTC)
    frm = quote(now.isoformat())
    to = quote((now - timedelta(days=1)).isoformat())  # from >= to
    r = await app_client.get(
        f"/admin/usage/timeseries?bucket=day&from={frm}&to={to}", headers=admin_headers
    )
    assert r.status_code == 400


# ----- T019 -----

@pytest.mark.asyncio
async def test_group_by_provider(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Two azure models + one openai model; group_by=provider sums each provider's
    # models (JOIN model_catalog ON slug == CallRecord.model).
    await _seed_catalog("azure/gpt-4o", "azure")
    await _seed_catalog("azure/gpt-4o-mini", "azure")
    await _seed_catalog("openai/o3", "openai")
    at = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
    await _seed_call(email="a@x.com", tokens=1000, cost="0.10", started_at=at, model="azure/gpt-4o")
    await _seed_call(email="b@x.com", tokens=500, cost="0.05", started_at=at, model="azure/gpt-4o-mini")
    await _seed_call(email="c@x.com", tokens=300, cost="0.03", started_at=at, model="openai/o3")

    frm = quote(datetime(2026, 5, 1, tzinfo=UTC).isoformat())
    to = quote(datetime(2026, 5, 31, tzinfo=UTC).isoformat())
    r = await app_client.get(
        f"/admin/usage?group_by=provider&from={frm}&to={to}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["group_by"] == "provider"
    items = {it["group_key"]: it for it in body["items"]}
    assert items["azure"]["total_tokens"] == 1500
    assert items["azure"]["call_count"] == 2
    assert items["openai"]["total_tokens"] == 300


async def _record_quarantine_event(
    allocation_id: str, details: dict[str, object] | None
) -> None:
    from ai_api.db import get_sessionmaker
    from ai_api.models import ActorType, AuditEventType, AuthAuditLog

    sm = get_sessionmaker()
    async with sm() as s:
        s.add(AuthAuditLog(
            id=str(ULID()),
            event_type=AuditEventType.allocation_quarantined,
            actor_type=ActorType.system,
            actor_id=None,
            target_type="allocation",
            target_id=allocation_id,
            source_ip=None,
            user_agent=None,
            request_id=None,
            created_at=datetime.now(UTC),
            details=details,
            redacted_message=None,
        ))
        await s.commit()


async def _create_allocation(client: AsyncClient, headers: dict[str, str]) -> str:
    r = await client.post(
        "/admin/allocations",
        headers=headers,
        json={"subject": "q@x.com", "resource_model": "gpt-4o-mini"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ----- T035 -----

@pytest.mark.asyncio
async def test_quarantine_reason_from_audit_details(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id = await _create_allocation(app_client, admin_headers)
    await _record_quarantine_event(
        alloc_id,
        {"trigger": "anomaly_detector", "last_hour_calls": 1100,
         "baseline_per_hour": 100, "reason": "ratio"},
    )
    r = await app_client.get(
        f"/admin/allocations/{alloc_id}/quarantine-reason", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["allocation_id"] == alloc_id
    assert body["event_type"] == "allocation_quarantined"
    assert body["last_hour_calls"] == 1100
    assert body["baseline_per_hour"] == 100
    assert body["reason"] == "ratio"
    assert "1100" in body["message"]
    assert "100" in body["message"]


# ----- T036 -----

@pytest.mark.asyncio
async def test_quarantine_reason_absent_details(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id = await _create_allocation(app_client, admin_headers)
    await _record_quarantine_event(alloc_id, None)  # legacy event without details
    r = await app_client.get(
        f"/admin/allocations/{alloc_id}/quarantine-reason", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message"] == "原因未記錄"
    assert body["last_hour_calls"] is None


# ----- T037 -----

@pytest.mark.asyncio
async def test_quarantine_reason_admin_only(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/allocations/01ABC/quarantine-reason")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_quarantine_reason_404(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get(
        "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ/quarantine-reason",
        headers=admin_headers,
    )
    assert r.status_code == 404


# ----- T046 (consolidated admin-only) -----

@pytest.mark.asyncio
async def test_viz_endpoints_admin_only(app_client: AsyncClient) -> None:
    frm = quote(datetime(2026, 5, 1, tzinfo=UTC).isoformat())
    to = quote(datetime(2026, 5, 31, tzinfo=UTC).isoformat())
    for path in (
        f"/admin/usage/timeseries?bucket=day&from={frm}&to={to}",
        f"/admin/usage/heatmap?from={frm}&to={to}",
        f"/admin/usage?group_by=provider&from={frm}&to={to}",
        "/admin/allocations/01ABC/quarantine-reason",
    ):
        r = await app_client.get(path)
        assert r.status_code in (401, 403), f"{path} -> {r.status_code}"
