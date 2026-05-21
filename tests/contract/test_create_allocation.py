"""Contract tests for POST /admin/allocations and GET /admin/allocations."""
from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


@pytest.mark.asyncio
async def test_create_allocation_201(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": "gpt-4o-mini"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert ULID_RE.match(body["id"])
    assert body["subject"] == "alice@example.com"
    assert body["resource_model"] == "gpt-4o-mini"
    assert body["status"] == "active"
    assert body["revoked_at"] is None
    assert body["created_by"] == "bootstrap-admin"
    assert body["token"].startswith("aiapi_")
    assert len(body["token"]) > len("aiapi_") + 16
    assert body["token_prefix"] == body["token"][:8]


@pytest.mark.asyncio
async def test_create_allocation_400_validation(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "", "resource_model": "gpt-4o-mini"},
    )
    assert response.status_code == 422  # FastAPI validation


@pytest.mark.asyncio
async def test_create_allocation_400_bad_model(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice", "resource_model": "has spaces!"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_allocation_401_no_admin_token(app_client: AsyncClient) -> None:
    response = await app_client.post(
        "/admin/allocations",
        json={"subject": "alice", "resource_model": "gpt-4o-mini"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_list_allocations(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    for subject in ("alice@example.com", "bob@example.com"):
        await app_client.post(
            "/admin/allocations",
            headers=admin_headers,
            json={"subject": subject, "resource_model": "gpt-4o-mini"},
        )
    response = await app_client.get("/admin/allocations", headers=admin_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 2
    subjects = {it["subject"] for it in items}
    assert {"alice@example.com", "bob@example.com"} <= subjects
    # listing must NOT include the plaintext token
    for it in items:
        assert "token" not in it
        assert "token_prefix" in it
