"""US3 traceability: anonymous reject + redaction in error_message."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anonymous_reject_has_null_allocation_id(app_client: AsyncClient) -> None:
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer aiapi_nope"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "x"}]},
    )
    assert r.status_code == 401

    sm = get_sessionmaker()
    async with sm() as s:
        rows = list((await s.execute(select(CallRecord))).scalars().all())
    assert any(
        row.allocation_id is None
        and row.outcome == CallOutcome.rejected_unauthenticated
        for row in rows
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_message_is_redacted(
    app_client: AsyncClient, admin_headers: dict[str, str], azure_key: str
) -> None:
    alloc = (
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "alice", "resource_model": "gpt-4o-mini"},
        )
    ).json()

    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.side_effect = RuntimeError(f"upstream failed with key={azure_key}")
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "x"}]},
        )
    assert r.status_code == 502
    assert azure_key not in r.text

    sm = get_sessionmaker()
    async with sm() as s:
        record = (
            await s.execute(
                select(CallRecord).where(CallRecord.outcome == CallOutcome.upstream_error)
            )
        ).scalar_one()
    assert record.error_message is not None
    assert azure_key not in record.error_message
    assert "***" in record.error_message
