"""Phase 19 device-flow — service-level contract (Foundational T003) + endpoint
contract (US1 T010/T012). This file starts with the service-level checks; the
endpoint checks live alongside once the API is wired.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from ai_api.db import get_sessionmaker
from ai_api.models import (
    DeviceAuthorization,
    DeviceAuthStatus,
    Member,
    MemberProvider,
    MemberStatus,
)
from ai_api.services.allocations import AllocationService
from ai_api.services.device_flow import DeviceFlowService


async def _member_with_allocation(email: str) -> tuple[str, str]:
    """Create a member + one allocation. Returns (member_id, allocation_id)."""
    sm = get_sessionmaker()
    async with sm() as s:
        member = Member(
            id=str(ULID()),
            email=email,
            provider=MemberProvider.external,
            display_name=email,
            status=MemberStatus.active,
            password_hash=None,
            created_at=datetime.now(UTC),
            disabled_at=None,
            created_by="test",
        )
        s.add(member)
        await s.flush()
        created = await AllocationService(s).create(
            member_id=member.id, resource_model="gpt-4o-mini"
        )
        await s.commit()
        return member.id, created.allocation.id


@pytest.mark.asyncio
async def test_authorize_then_pending_then_slow_down(app_client: AsyncClient) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        svc = DeviceFlowService(s)
        auth = await svc.authorize(device_label="Codex on host-x")
        await s.commit()
        assert auth.user_code and "-" in auth.user_code
        assert auth.device_code and auth.expires_in == 600 and auth.interval == 5

    async with sm() as s:
        svc = DeviceFlowService(s)
        first = await svc.poll(auth.device_code)
        await s.commit()
        assert first.status == "authorization_pending"
    async with sm() as s:
        svc = DeviceFlowService(s)
        # Immediate second poll (< interval) → slow_down.
        second = await svc.poll(auth.device_code)
        await s.commit()
        assert second.status == "slow_down"


@pytest.mark.asyncio
async def test_approve_owner_then_single_delivery(app_client: AsyncClient) -> None:
    member_id, alloc_id = await _member_with_allocation("alice@x.com")
    sm = get_sessionmaker()
    async with sm() as s:
        auth = await DeviceFlowService(s).authorize(device_label="Codex on mac")
        await s.commit()

    async with sm() as s:
        member = await s.get(Member, member_id)
        assert member is not None
        row = await DeviceFlowService(s).approve(auth.user_code, member, [alloc_id])
        await s.commit()
        assert row.status == DeviceAuthStatus.approved
        assert row.credential_id is not None

    async with sm() as s:
        res = await DeviceFlowService(s).poll(auth.device_code)
        await s.commit()
        assert res.status == "success"
        assert res.token and res.token.startswith("aiapi_")
        assert res.credential_id

    # Second poll → already delivered → expired_token.
    async with sm() as s:
        again = await DeviceFlowService(s).poll(auth.device_code)
        await s.commit()
        assert again.status == "expired_token"


@pytest.mark.asyncio
async def test_approve_non_owner_raises_and_mints_nothing(app_client: AsyncClient) -> None:
    _alice_id, alice_alloc = await _member_with_allocation("alice@x.com")
    bob_id, _bob_alloc = await _member_with_allocation("bob@x.com")
    sm = get_sessionmaker()
    async with sm() as s:
        auth = await DeviceFlowService(s).authorize()
        await s.commit()

    async with sm() as s:
        bob = await s.get(Member, bob_id)
        assert bob is not None
        with pytest.raises(PermissionError):
            await DeviceFlowService(s).approve(auth.user_code, bob, [alice_alloc])
        await s.rollback()

    # No credential minted on alice's allocation by the failed approve.
    async with sm() as s:
        creds = await AllocationService(s).list_credentials(alice_alloc)
        assert len(list(creds)) == 1  # only the default from create()


@pytest.mark.asyncio
async def test_deny_then_access_denied(app_client: AsyncClient) -> None:
    member_id, _alloc = await _member_with_allocation("carol@x.com")
    sm = get_sessionmaker()
    async with sm() as s:
        auth = await DeviceFlowService(s).authorize()
        await s.commit()
    async with sm() as s:
        member = await s.get(Member, member_id)
        assert member is not None
        assert await DeviceFlowService(s).deny(auth.user_code, member) is True
        await s.commit()
    async with sm() as s:
        res = await DeviceFlowService(s).poll(auth.device_code)
        assert res.status == "access_denied"


@pytest.mark.asyncio
async def test_expired_request_polls_expired(app_client: AsyncClient) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        auth = await DeviceFlowService(s).authorize()
        await s.commit()
    # Force expiry by back-dating expires_at.
    async with sm() as s:
        row = (
            await s.execute(
                select(DeviceAuthorization).where(
                    DeviceAuthorization.device_code == auth.device_code
                )
            )
        ).scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    async with sm() as s:
        res = await DeviceFlowService(s).poll(auth.device_code)
        await s.commit()
        assert res.status == "expired_token"


# ---------------------------------------------------------------------------
# US1 — HTTP endpoint contract
# ---------------------------------------------------------------------------

from unittest.mock import patch  # noqa: E402

from ai_api.api.deps import CSRF_HEADER  # noqa: E402


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get("aiapi_csrf") or ""}


def _stub() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


async def _login_member_with_allocation(
    client: AsyncClient, admin_headers: dict[str, str], email: str
) -> str:
    """Create + login a member, give them one allocation. Returns allocation_id."""
    await client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": email,
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    await client.post("/auth/local/login", json={"email": email, "password": "VerySafePass123"})
    me = (await client.get("/me")).json()
    alloc = (
        await client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"member_id": me["id"], "resource_model": "gpt-4o-mini"},
        )
    ).json()
    return alloc["id"]


@pytest.mark.asyncio
async def test_authorize_endpoint_and_token_pending(app_client: AsyncClient) -> None:
    r = await app_client.post("/device/authorize", json={"device_label": "Codex on host"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["device_code"] and "-" in body["user_code"]
    assert body["verification_uri"] == "/device"
    assert body["expires_in"] == 600 and body["interval"] == 5

    p1 = await app_client.post("/device/token", json={"device_code": body["device_code"]})
    assert p1.status_code == 400
    assert p1.json()["error"] == "authorization_pending"
    p2 = await app_client.post("/device/token", json={"device_code": body["device_code"]})
    assert p2.status_code == 400
    assert p2.json()["error"] == "slow_down"


@pytest.mark.asyncio
async def test_device_flow_happy_path_endpoints(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    alloc_id = await _login_member_with_allocation(app_client, admin_headers, "alice@x.com")
    auth = (
        await app_client.post("/device/authorize", json={"device_label": "Codex on mac"})
    ).json()

    # Member approves, picking the allocation.
    appr = await app_client.post(
        f"/me/device/{auth['user_code']}/approve",
        headers=_csrf(app_client),
        json={"allocation_ids": [alloc_id]},
    )
    assert appr.status_code == 204, appr.text

    # CLI polls → gets the plaintext token once.
    tok = await app_client.post("/device/token", json={"device_code": auth["device_code"]})
    assert tok.status_code == 200, tok.text
    tb = tok.json()
    assert tb["token"].startswith("aiapi_") and tb["credential_id"]

    # The delivered token can call the proxy.
    with patch("ai_api.proxy.upstream.acompletion") as mock:
        mock.return_value = _stub()
        call = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {tb['token']}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert call.status_code == 200

    # Second poll → already delivered.
    again = await app_client.post("/device/token", json={"device_code": auth["device_code"]})
    assert again.status_code == 400
    assert again.json()["error"] == "expired_token"


@pytest.mark.asyncio
async def test_device_flow_credential_listed_and_revocable(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """US4: the minted credential shows in the device list (named, no plaintext)
    and is independently revocable (Phase 18)."""
    alloc_id = await _login_member_with_allocation(app_client, admin_headers, "dora@x.com")
    auth = (
        await app_client.post("/device/authorize", json={"device_label": "Codex on dora-pc"})
    ).json()
    await app_client.post(
        f"/me/device/{auth['user_code']}/approve",
        headers=_csrf(app_client),
        json={"allocation_ids": [alloc_id]},
    )
    tok = (await app_client.post("/device/token", json={"device_code": auth["device_code"]})).json()

    creds = (await app_client.get(f"/me/allocations/{alloc_id}/credentials")).json()
    assert {"預設", "Codex on dora-pc"} == {c["name"] for c in creds}
    minted = next(c for c in creds if c["name"] == "Codex on dora-pc")
    assert "token" not in minted  # no plaintext in the list

    # The minted token works, then revoking it kills only that one.
    async def _call(token: str) -> int:
        with patch("ai_api.proxy.upstream.acompletion") as mock:
            mock.return_value = _stub()
            r = await app_client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
            )
        return r.status_code

    assert await _call(tok["token"]) == 200
    r = await app_client.request(
        "DELETE",
        f"/me/allocations/{alloc_id}/credentials/{minted['id']}",
        headers=_csrf(app_client),
    )
    assert r.status_code == 204
    assert await _call(tok["token"]) == 401  # revoked device → rejected
