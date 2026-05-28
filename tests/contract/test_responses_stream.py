"""Streaming + disconnect tests for /v1/responses (Phase 11 US1)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord, ModelCatalog

RESP_MODEL = "azure/gpt-5"


class _Ev:
    def __init__(self, type_: str, payload: dict, response: dict | None = None) -> None:
        self.type = type_
        self._payload = payload
        self.response = response

    def model_dump_json(self) -> str:
        return json.dumps(self._payload)


async def _seed(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(ModelCatalog(
            slug=RESP_MODEL, provider="azure", display_name=RESP_MODEL, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=["responses"], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
        ))
        await s.commit()
    r = await client.post(
        "/admin/providers", headers=admin_headers,
        json={"provider": "azure", "label": "t", "api_key": "az-test-12345678"},
    )
    assert r.status_code in (200, 201), r.text
    a = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": RESP_MODEL},
    )
    assert a.status_code == 201, a.text
    return a.json()


def _completed_event() -> _Ev:
    resp = {
        "id": "resp_stream",
        "usage": {
            "input_tokens": 8, "output_tokens": 12, "total_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 3},
            "input_tokens_details": {"cached_tokens": 2},
        },
    }
    return _Ev("response.completed", {"type": "response.completed", "response": resp}, response=resp)


@pytest.mark.asyncio
async def test_responses_stream_forwards_and_records(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _seed(app_client, admin_headers)

    async def _fake(*a, **k):
        async def gen():
            yield _Ev("response.created", {"type": "response.created"})
            yield _Ev("response.output_text.delta", {"type": "response.output_text.delta", "delta": "hi"})
            yield _completed_event()
        return gen()

    with patch("ai_api.proxy.upstream.aresponses", new=_fake):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RESP_MODEL, "input": "hi", "stream": True},
        )
    assert r.status_code == 200, r.text
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "event: response.completed" in body
    assert "response.output_text.delta" in body

    sm = get_sessionmaker()
    async with sm() as s:
        rec = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
        )).scalar_one()
    assert rec.prompt_tokens == 8
    assert rec.completion_tokens == 12
    assert rec.reasoning_tokens == 3
    assert rec.cached_tokens == 2


@pytest.mark.asyncio
async def test_responses_stream_cut_still_records(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Stream ends without a completed event (simulated cut) → usage still recorded."""
    alloc = await _seed(app_client, admin_headers)

    async def _fake(*a, **k):
        async def gen():
            yield _Ev("response.created", {"type": "response.created"})
            yield _Ev("response.output_text.delta", {"type": "response.output_text.delta", "delta": "h"})
            # no response.completed — simulates an interrupted stream
        return gen()

    with patch("ai_api.proxy.upstream.aresponses", new=_fake):
        r = await app_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": RESP_MODEL, "input": "hi", "stream": True},
        )
    assert r.status_code == 200
    sm = get_sessionmaker()
    async with sm() as s:
        rec = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
        )).scalar_one()
    # Recorded even without usage (null tokens) per FR-017.
    assert rec.prompt_tokens is None
