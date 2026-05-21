"""US1 SC-003: Azure OpenAI key must never appear in response body/headers/logs."""
from __future__ import annotations

import io
import logging
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.observability.logging import JsonFormatter, RedactionFilter


async def _make_allocation(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    response = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": "gpt-4o-mini"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def captured_logs(azure_key: str) -> tuple[logging.Handler, io.StringIO]:
    """Attach a stream handler to root logger and return (handler, buffer)."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter(secrets=[azure_key]))
    root = logging.getLogger()
    root.addHandler(handler)
    yield handler, buf
    root.removeHandler(handler)


def _scan(text: str, secret: str) -> bool:
    return secret in text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_success_response_does_not_leak_key(
    app_client: AsyncClient, admin_headers: dict[str, str], azure_key: str
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)

    stub = {
        "id": "chatcmpl",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = stub
        resp = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert resp.status_code == 200
    body_text = resp.text
    headers_text = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
    assert not _scan(body_text, azure_key)
    assert not _scan(headers_text, azure_key)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "no_token",
        "bad_token",
        "model_mismatch",
        "upstream_error",
    ],
)
async def test_error_paths_do_not_leak_key(
    app_client: AsyncClient,
    admin_headers: dict[str, str],
    azure_key: str,
    scenario: str,
) -> None:
    alloc = await _make_allocation(app_client, admin_headers)
    headers: dict[str, str] = {}
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}

    if scenario == "no_token":
        pass
    elif scenario == "bad_token":
        headers["Authorization"] = "Bearer aiapi_nope"
    elif scenario == "model_mismatch":
        headers["Authorization"] = f"Bearer {alloc['token']}"
        body["model"] = "gpt-4-different"
    elif scenario == "upstream_error":
        headers["Authorization"] = f"Bearer {alloc['token']}"
        # Will be patched below
    else:
        raise AssertionError(scenario)

    if scenario == "upstream_error":
        with patch("ai_api.proxy.upstream.acompletion") as mock:
            mock.side_effect = RuntimeError(f"upstream failed with key={azure_key}")
            resp = await app_client.post("/v1/chat/completions", headers=headers, json=body)
    else:
        resp = await app_client.post("/v1/chat/completions", headers=headers, json=body)

    body_text = resp.text
    headers_text = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
    assert azure_key not in body_text, f"key leaked in body for {scenario}: {body_text}"
    assert azure_key not in headers_text, f"key leaked in headers for {scenario}"
