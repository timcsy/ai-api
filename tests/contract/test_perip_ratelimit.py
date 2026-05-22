"""Contract tests for per-IP rate limit (FR-013, US6)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_perip_lockout_after_10_failures(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # All requests from app_client share the same source IP (127.0.0.1 by default
    # via ASGITransport — actually it's empty; the test relies on that consistency).
    # First, 10 attempts at distinct emails — all 401 (unknown email)
    for i in range(10):
        r = await app_client.post(
            "/auth/local/login",
            json={"email": f"nobody{i}@nowhere.com", "password": "x"},
        )
        assert r.status_code == 401, f"attempt {i + 1} unexpectedly {r.status_code}"

    # 11th attempt — even with a valid (but unrelated) email — should 429
    r = await app_client.post(
        "/auth/local/login",
        json={"email": "valid-but-locked@x.com", "password": "x"},
    )
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_ip_lock_blocks_even_correct_password(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Create a local member with a known password
    await app_client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": "real@x.com",
            "provider": "local_password",
            "initial_password": "RealPass2026",
            "send_invitation": False,
        },
    )
    # Burn 10 failures from this IP
    for i in range(10):
        await app_client.post(
            "/auth/local/login",
            json={"email": f"x{i}@y.com", "password": "wrong"},
        )
    # Now try with the CORRECT password — should still be locked
    r = await app_client.post(
        "/auth/local/login",
        json={"email": "real@x.com", "password": "RealPass2026"},
    )
    assert r.status_code == 429
