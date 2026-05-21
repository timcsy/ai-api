"""SC-003 global scan: Azure OpenAI key must not appear in ANY public endpoint response."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.config import get_settings


@pytest.fixture
def azure_key() -> str:
    return get_settings().azure_openai_api_key


async def _create(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    r = await client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "scan@example.com", "resource_model": "gpt-4o-mini"},
    )
    return r.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "openapi_doc",
        "healthz",
        "create_allocation",
        "list_allocations",
        "list_calls_404",
        "revoke_404",
        "proxy_no_token",
        "proxy_bad_token",
        "proxy_revoked",
        "proxy_model_mismatch",
        "proxy_upstream_error",
    ],
)
async def test_no_key_leak_for_scenario(
    app_client: AsyncClient,
    admin_headers: dict[str, str],
    azure_key: str,
    scenario: str,
) -> None:
    if scenario == "openapi_doc":
        r = await app_client.get("/openapi.json")
    elif scenario == "healthz":
        r = await app_client.get("/healthz")
    elif scenario == "create_allocation":
        r = await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": "s", "resource_model": "gpt-4o-mini"},
        )
    elif scenario == "list_allocations":
        r = await app_client.get("/admin/allocations", headers=admin_headers)
    elif scenario == "list_calls_404":
        r = await app_client.get(
            "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ/calls", headers=admin_headers
        )
    elif scenario == "revoke_404":
        r = await app_client.delete(
            "/admin/allocations/01ZZZZZZZZZZZZZZZZZZZZZZZZ", headers=admin_headers
        )
    elif scenario == "proxy_no_token":
        r = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": []},
        )
    elif scenario == "proxy_bad_token":
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer aiapi_no"},
            json={"model": "gpt-4o-mini", "messages": []},
        )
    elif scenario == "proxy_revoked":
        alloc = await _create(app_client, admin_headers)
        await app_client.delete(f"/admin/allocations/{alloc['id']}", headers=admin_headers)
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "x"}]},
        )
    elif scenario == "proxy_model_mismatch":
        alloc = await _create(app_client, admin_headers)
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "different", "messages": [{"role": "user", "content": "x"}]},
        )
    elif scenario == "proxy_upstream_error":
        alloc = await _create(app_client, admin_headers)
        with patch("ai_api.proxy.upstream.acompletion") as mock:
            mock.side_effect = RuntimeError(f"upstream failed: api_key={azure_key} endpoint=...")
            r = await app_client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {alloc['token']}"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "x"}]},
            )
    else:
        raise AssertionError(scenario)

    body_text = r.text
    headers_text = "\n".join(f"{k}: {v}" for k, v in r.headers.items())
    assert azure_key not in body_text, f"key leaked in body for {scenario}"
    assert azure_key not in headers_text, f"key leaked in headers for {scenario}"
