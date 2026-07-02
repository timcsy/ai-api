"""Spec 055: local login accepts a username (non-email) identifier."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_local(client: AsyncClient, admin_headers: dict, ident: str) -> int:
    r = await client.post(
        "/admin/members",
        headers=admin_headers,
        json={
            "email": ident,
            "provider": "local_password",
            "initial_password": "VerySafePass123",
            "send_invitation": False,
        },
    )
    return r.status_code


@pytest.mark.asyncio
async def test_username_login_success(app_client: AsyncClient, admin_headers) -> None:
    assert await _create_local(app_client, admin_headers, "alice") == 201
    r = await app_client.post(
        "/auth/local/login", json={"email": "alice", "password": "VerySafePass123"}
    )
    assert r.status_code == 200, r.text
    me = (await app_client.get("/me")).json()
    assert me["email"] == "alice"


@pytest.mark.asyncio
async def test_username_wrong_password_generic_401(app_client: AsyncClient, admin_headers) -> None:
    await _create_local(app_client, admin_headers, "bob")
    r = await app_client.post("/auth/local/login", json={"email": "bob", "password": "WrongPass999"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_username_case_insensitive(app_client: AsyncClient, admin_headers) -> None:
    assert await _create_local(app_client, admin_headers, "Carol") == 201  # stored lowercased
    r = await app_client.post(
        "/auth/local/login", json={"email": "carol", "password": "VerySafePass123"}
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_create_rejects_bad_identifier(app_client: AsyncClient, admin_headers) -> None:
    assert await _create_local(app_client, admin_headers, "has space") == 400
    assert await _create_local(app_client, admin_headers, "bad@") == 400  # '@' but not an email


@pytest.mark.asyncio
async def test_email_identifier_still_works(app_client: AsyncClient, admin_headers) -> None:
    assert await _create_local(app_client, admin_headers, "dave@x.com") == 201
    r = await app_client.post(
        "/auth/local/login", json={"email": "dave@x.com", "password": "VerySafePass123"}
    )
    assert r.status_code == 200, r.text
