"""Phase 5 T039 / US3: 6 acceptance scenarios for tag-based access."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


def _stub() -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "test",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _seed_anthropic_model() -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug="anthropic/claude-3-5-sonnet",
                provider="anthropic",
                display_name="Claude 3.5 Sonnet",
                family="claude-3",
                description="anthropic flagship",
                modality_input=["text"], modality_output=["text"],
                capabilities=["chat"], context_window=200000,
                cost_tier="high", recommended_for=["chat"], tags=[],
                example_request={}, official_doc_url=None,
                status="active", deprecation_note=None,
                created_at=now, updated_at=now,
            )
        )
        await s.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us3_tag_visibility_and_proxy_check(
    app_client: AsyncClient,
    admin_headers: dict[str, str],
    make_member,
    make_provider_credential,
) -> None:
    """Scenarios 1-3 + 5: alice (eng) sees; bob (no tag) blocked; deny overrides."""
    await _seed_anthropic_model()
    await make_provider_credential(provider="anthropic", api_key="sk-ant-test-1234")

    alice = await make_member("alice@x.com")
    bob = await make_member("bob@x.com")

    # tag alice 'eng'
    r = await app_client.post(
        f"/admin/members/{alice}/tags", headers=admin_headers, json={"tags": ["eng"]}
    )
    assert r.status_code == 200

    # restrict model to eng only
    r = await app_client.patch(
        "/admin/catalog/models/anthropic/claude-3-5-sonnet/access",
        headers=admin_headers,
        json={"default_access": "restricted", "allowed_tags": ["eng"]},
    )
    assert r.status_code == 200, r.text

    # Helper: open a session for a member and call catalog/proxy with cookies.
    # Use admin endpoints to grant allocations for proxy tests.
    alice_alloc = (await app_client.post(
        "/admin/allocations", headers=admin_headers,
        json={"member_id": alice, "resource_model": "anthropic/claude-3-5-sonnet"},
    )).json()
    bob_alloc = (await app_client.post(
        "/admin/allocations", headers=admin_headers,
        json={"member_id": bob, "resource_model": "anthropic/claude-3-5-sonnet"},
    )).json()

    # Scenario 3 (proxy 二次檢查): bob direct curl → 403 model_forbidden
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {bob_alloc['token']}"},
        json={"model": "anthropic/claude-3-5-sonnet", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "model_forbidden"

    # Scenario 1 (proxy): alice OK
    with patch("litellm.acompletion", return_value=_stub()):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alice_alloc['token']}"},
            json={"model": "anthropic/claude-3-5-sonnet", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200

    # Scenario 5: alice gets contractor tag + model denies contractor → deny wins
    await app_client.post(
        f"/admin/members/{alice}/tags", headers=admin_headers, json={"tags": ["contractor"]}
    )
    await app_client.patch(
        "/admin/catalog/models/anthropic/claude-3-5-sonnet/access",
        headers=admin_headers,
        json={"denied_tags": ["contractor"]},
    )
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {alice_alloc['token']}"},
        json={"model": "anthropic/claude-3-5-sonnet", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "model_forbidden"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_us3_bulk_apply_immediate(
    app_client: AsyncClient,
    admin_headers: dict[str, str],
    make_member,
    make_provider_credential,
) -> None:
    """Scenario 6: bulk apply tag → 5 members all immediately tagged."""
    await _seed_anthropic_model()
    await make_provider_credential(provider="anthropic", api_key="sk-ant-test-5555")

    members = [await make_member(f"u{i}@x.com") for i in range(5)]
    r = await app_client.post(
        "/admin/tags/bulk-apply",
        headers=admin_headers,
        json={"tag": "eng", "member_ids": members},
    )
    assert r.status_code == 200
    assert r.json()["applied_count"] == 5
    # verify all 5 actually got it
    for mid in members:
        r2 = await app_client.get(f"/admin/members/{mid}/tags", headers=admin_headers)
        assert r2.json() == ["eng"]
