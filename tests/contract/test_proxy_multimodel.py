"""Phase 20 Foundational/US2 — one application key, many models.

A credential scoped to allocations A+B can call both models; each call meters to
the matching allocation. A model outside the key's scope is refused
(model_mismatch) and bills nothing.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import Member, MemberProvider, MemberStatus
from ai_api.services.allocations import AllocationService


async def _member_scoped(models: list[str]) -> str:
    """Member + one key scoped to allocations for each of `models`. Returns token."""
    sm = get_sessionmaker()
    async with sm() as s:
        member = Member(
            id=str(ULID()), email=f"{ULID()}@x.com", provider=MemberProvider.external,
            display_name="p", status=MemberStatus.active, password_hash=None,
            created_at=datetime.now(UTC), disabled_at=None, created_by="test",
        )
        s.add(member)
        await s.flush()
        svc = AllocationService(s)
        ids = [(await svc.create(member_id=member.id, resource_model=m)).allocation.id for m in models]
        _cred, token = await svc.create_member_credential(member.id, "app", ids)
        await s.commit()
        return token.plaintext


def _stub(model: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _member_two_allocations() -> tuple[str, str, str, str]:
    """Member with two allocations (gpt-4o-mini, gpt-4o). Returns
    (member_id, alloc_a_id, alloc_b_id, token) for a key scoped to BOTH."""
    sm = get_sessionmaker()
    async with sm() as s:
        member = Member(
            id=str(ULID()),
            email="multi@x.com",
            provider=MemberProvider.external,
            display_name="multi",
            status=MemberStatus.active,
            password_hash=None,
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            disabled_at=None,
            created_by="test",
        )
        s.add(member)
        await s.flush()
        svc = AllocationService(s)
        a = (await svc.create(member_id=member.id, resource_model="gpt-4o-mini")).allocation
        b = (await svc.create(member_id=member.id, resource_model="gpt-4o")).allocation
        _cred, token = await svc.create_member_credential(
            member.id, "my-app", [a.id, b.id]
        )
        await s.commit()
        return member.id, a.id, b.id, token.plaintext


async def _call(client: AsyncClient, token: str, model: str) -> int:
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub(model)
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
        )
    return r.status_code


@pytest.mark.asyncio
async def test_one_key_two_models_meter_to_their_allocations(app_client: AsyncClient) -> None:
    _m, a_id, b_id, token = await _member_two_allocations()

    assert await _call(app_client, token, "gpt-4o-mini") == 200
    assert await _call(app_client, token, "gpt-4o") == 200
    assert await _call(app_client, token, "gpt-4o-mini") == 200

    # Each call metered to the matching allocation.
    sm = get_sessionmaker()
    async with sm() as s:
        from ai_api.services.records import RecordsService

        a_calls = await RecordsService(s).list_for_allocation(a_id, limit=10)
        b_calls = await RecordsService(s).list_for_allocation(b_id, limit=10)
        assert len(a_calls) == 2  # two gpt-4o-mini calls
        assert len(b_calls) == 1  # one gpt-4o call


@pytest.mark.asyncio
async def test_model_outside_scope_is_refused(app_client: AsyncClient) -> None:
    _m, _a, _b, token = await _member_two_allocations()
    # gpt-4o-mini and gpt-4o are in scope; a third model is not.
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "gpt-4-turbo", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "model_mismatch"
    # The message is actionable: it names the in-scope models and points at /model
    # so a stray Codex /model pick gives "switch to X", not a cryptic failure.
    assert "gpt-4o-mini" in err["message"] and "gpt-4o" in err["message"]
    assert "/model" in err["message"]


@pytest.mark.asyncio
async def test_bare_codex_slug_aliases_to_prefixed_scope_model(app_client: AsyncClient) -> None:
    # A key scoped to azure/gpt-5.4 is callable with Codex's bare slug gpt-5.4.
    token = await _member_scoped(["azure/gpt-5.4"])
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub("azure/gpt-5.4")
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "gpt-5.4", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200, r.text
    # Upstream gets the canonical prefixed model so litellm routes to azure.
    assert mock.call_args.kwargs["model"] == "azure/gpt-5.4"


@pytest.mark.asyncio
async def test_ambiguous_bare_slug_is_refused(app_client: AsyncClient) -> None:
    # Same bare slug under two providers → no aliasing; the request is refused.
    token = await _member_scoped(["azure/gpt-4o", "openai/gpt-4o"])
    r = await app_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "model_mismatch"
