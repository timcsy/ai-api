"""Contract tests for /admin/whitelist, /admin/rules, /admin/source-restrictions."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_whitelist_crud(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # 401 without admin token
    r = await app_client.post("/admin/whitelist", json={"email": "x@y.com"})
    assert r.status_code == 401

    # add
    r = await app_client.post(
        "/admin/whitelist",
        headers=admin_headers,
        json={"email": "Alice@Example.com", "note": "alpha"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"

    # list
    r = await app_client.get("/admin/whitelist", headers=admin_headers)
    assert any(e["email"] == "alice@example.com" for e in r.json())

    # remove
    r = await app_client.delete("/admin/whitelist/alice@example.com", headers=admin_headers)
    assert r.status_code == 204

    r = await app_client.get("/admin/whitelist", headers=admin_headers)
    assert not any(e["email"] == "alice@example.com" for e in r.json())


@pytest.mark.asyncio
async def test_rules_crud(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post(
        "/admin/rules",
        headers=admin_headers,
        json={"rule_type": "email_domain", "pattern": "Example.com"},
    )
    assert r.status_code == 201
    rid = r.json()["id"]
    assert r.json()["pattern"] == "example.com"

    r = await app_client.get("/admin/rules", headers=admin_headers)
    assert any(it["id"] == rid for it in r.json())

    r = await app_client.delete(f"/admin/rules/{rid}", headers=admin_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_source_restrictions_crud(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/source-restrictions",
        headers=admin_headers,
        json={"cidr": "10.0.0.0/8"},
    )
    assert r.status_code == 201
    rid = r.json()["id"]

    r = await app_client.get("/admin/source-restrictions", headers=admin_headers)
    assert any(it["id"] == rid for it in r.json())

    r = await app_client.delete(f"/admin/source-restrictions/{rid}", headers=admin_headers)
    assert r.status_code == 204
