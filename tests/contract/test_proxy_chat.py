"""Contract tests for POST /v1/chat/completions."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord


async def _make_allocation(
    client: AsyncClient, admin_headers: dict[str, str], model: str = "gpt-4o-mini"
) -> dict:
    response = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _stub_litellm_response() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.asyncio
async def test_proxy_chat_200(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub_litellm_response()
        response = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "hello"


@pytest.mark.asyncio
async def test_proxy_chat_401_no_token(app_client: AsyncClient) -> None:
    response = await app_client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": []},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_proxy_chat_401_bad_token(app_client: AsyncClient) -> None:
    response = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer aiapi_nope"},
        json={"model": "gpt-4o-mini", "messages": []},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_proxy_chat_403_model_mismatch(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers, model="gpt-4o-mini")
    response = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alloc['token']}"},
        json={
            "model": "gpt-4-different",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "model_mismatch"


@pytest.mark.asyncio
async def test_proxy_chat_forwards_passthrough_params(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Optional chat params (temperature/max_tokens/tools/...) must reach upstream —
    the earlier handler forwarded ONLY messages, silently dropping them."""
    alloc = await _make_allocation(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub_litellm_response()
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.2, "max_tokens": 64,
                "tools": [{"type": "function", "function": {"name": "f"}}],
            },
        )
    assert r.status_code == 200, r.text
    kwargs = mock.call_args.kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 64
    assert kwargs["tools"][0]["function"]["name"] == "f"
    assert kwargs["drop_params"] is True  # unsupported params dropped, not 400'd
    assert "stream" not in kwargs  # non-streaming path


@pytest.mark.asyncio
async def test_proxy_chat_retries_dropping_rejected_param(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """A reasoning model (custom Azure deployment name litellm can't map) 400s on
    temperature != 1 — the handler drops the named param and retries instead of
    502-ing. Regression: forwarding temperature broke reasoning models."""
    alloc = await _make_allocation(app_client, admin_headers)
    calls: list[dict] = []

    async def _fake(*a, **k):
        calls.append(k)
        if "temperature" in k:
            raise RuntimeError(
                "litellm.BadRequestError: AzureException BadRequestError - "
                "Unsupported value: 'temperature' does not support 0.4 with this "
                "model. Only the default (1) value is supported."
            )
        return _stub_litellm_response()

    with patch("ai_api.proxy.upstream.acompletion", new=_fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.4,
            },
        )
    assert r.status_code == 200, r.text
    assert len(calls) == 2  # first with temperature (rejected), retry without
    assert "temperature" in calls[0] and "temperature" not in calls[1]


# --- streaming (SSE) -------------------------------------------------------


class _Chunk:
    def __init__(self, payload: dict) -> None:
        self._p = payload

    def model_dump_json(self) -> str:
        return json.dumps(self._p)


def _delta(content: str) -> _Chunk:
    return _Chunk({
        "id": "chatcmpl-x", "object": "chat.completion.chunk", "model": "gpt-4o-mini",
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
        "usage": None,
    })


def _usage_chunk() -> _Chunk:
    return _Chunk({
        "id": "chatcmpl-x", "object": "chat.completion.chunk", "model": "gpt-4o-mini",
        "choices": [],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    })


def _usage_chunk_with_choice() -> _Chunk:
    # Azure/litellm attach usage to a choices-PRESENT chunk (not the OpenAI
    # canonical choices-empty terminal chunk).
    return _Chunk({
        "id": "chatcmpl-x", "object": "chat.completion.chunk", "model": "gpt-4o-mini",
        "choices": [{"index": 0, "delta": {"content": None}, "finish_reason": None}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    })


async def _last_success_record() -> CallRecord:
    sm = get_sessionmaker()
    async with sm() as s:
        return (await s.execute(
            select(CallRecord).where(CallRecord.outcome == CallOutcome.success)
            .order_by(CallRecord.started_at.desc())
        )).scalars().first()


@pytest.mark.asyncio
async def test_proxy_chat_stream_forwards_and_records(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)

    async def _fake(*a, **k):
        # billing must force include_usage upstream even if the client didn't ask
        assert k["stream"] is True
        assert k["stream_options"]["include_usage"] is True

        async def gen():
            yield _delta("hel")
            yield _delta("lo")
            yield _usage_chunk()
        return gen()

    with patch("ai_api.proxy.upstream.acompletion", new=_fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
    assert r.status_code == 200, r.text
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert '"content": "hel"' in body
    assert body.rstrip().endswith("data: [DONE]")
    # client did NOT ask for usage → the usage-only chunk is stripped on relay
    assert '"prompt_tokens": 5' not in body
    # …but billing still recorded from it
    rec = await _last_success_record()
    assert rec.prompt_tokens == 5 and rec.completion_tokens == 7 and rec.total_tokens == 12


@pytest.mark.asyncio
async def test_proxy_chat_stream_include_usage_forwarded(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)

    async def _fake(*a, **k):
        async def gen():
            yield _delta("hi")
            yield _usage_chunk()
        return gen()

    with patch("ai_api.proxy.upstream.acompletion", new=_fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True, "stream_options": {"include_usage": True},
            },
        )
    assert r.status_code == 200
    # client asked for usage → the usage chunk IS forwarded
    assert '"prompt_tokens": 5' in r.text


@pytest.mark.asyncio
async def test_proxy_chat_stream_nulls_usage_on_choices_present_chunk(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """When the provider attaches usage to a choices-present chunk and the client
    didn't ask for usage, forward the chunk with usage nulled (not leaked) — but
    still bill from it."""
    alloc = await _make_allocation(app_client, admin_headers)

    async def _fake(*a, **k):
        async def gen():
            yield _delta("hi")
            yield _usage_chunk_with_choice()
        return gen()

    with patch("ai_api.proxy.upstream.acompletion", new=_fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
    assert r.status_code == 200
    body = r.text
    assert '"prompt_tokens": 5' not in body  # usage nulled, not leaked
    assert '"usage": null' in body            # the choices-present chunk still forwarded
    rec = await _last_success_record()
    assert rec.prompt_tokens == 5 and rec.completion_tokens == 7  # billed anyway


@pytest.mark.asyncio
async def test_proxy_chat_stream_cut_still_records(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Stream ends without a usage chunk (cut/provider emitted none) → still recorded."""
    alloc = await _make_allocation(app_client, admin_headers)

    async def _fake(*a, **k):
        async def gen():
            yield _delta("h")
            # no usage chunk
        return gen()

    with patch("ai_api.proxy.upstream.acompletion", new=_fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
    assert r.status_code == 200
    rec = await _last_success_record()
    assert rec is not None and rec.prompt_tokens is None
