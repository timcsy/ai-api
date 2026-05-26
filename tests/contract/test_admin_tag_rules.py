"""Phase 5.2 T008 / US1: contract tests for admin tag-rule endpoints.

Contract: specs/014-auto-tag-rules/contracts/tag-rules.yaml
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create(client, headers, **body):
    return await client.post("/admin/tag-rules", headers=headers, json=body)


@pytest.mark.asyncio
async def test_list_empty(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.get("/admin/tag-rules", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_requires_admin(app_client: AsyncClient) -> None:
    r = await app_client.get("/admin/tag-rules")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_and_list_ordered(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r1 = await _create(
        app_client, admin_headers,
        matcher_type="email_localpart_regex", pattern=r"[a-z]{0,2}\d{6,}", tag="student",
    )
    assert r1.status_code == 201, r1.text
    r2 = await _create(app_client, admin_headers, matcher_type="always", tag="teacher")
    assert r2.status_code == 201

    lst = await app_client.get("/admin/tag-rules", headers=admin_headers)
    rows = lst.json()
    assert [row["tag"] for row in rows] == ["student", "teacher"]
    assert rows[0]["order_index"] < rows[1]["order_index"]


@pytest.mark.asyncio
async def test_create_unsafe_regex_rejected(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await _create(
        app_client, admin_headers,
        matcher_type="email_localpart_regex", pattern="(a+)+$", tag="bad",
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "unsafe_regex"


@pytest.mark.asyncio
async def test_create_invalid_tag_rejected(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await _create(app_client, admin_headers, matcher_type="always", tag="UPPER")
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "invalid_tag"


@pytest.mark.asyncio
async def test_patch_updates(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    c = await _create(app_client, admin_headers, matcher_type="always", tag="teacher")
    rid = c.json()["id"]
    r = await app_client.patch(
        f"/admin/tag-rules/{rid}", headers=admin_headers, json={"enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False


@pytest.mark.asyncio
async def test_patch_unknown_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.patch("/admin/tag-rules/nope", headers=admin_headers, json={"enabled": False})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    c = await _create(app_client, admin_headers, matcher_type="always", tag="teacher")
    rid = c.json()["id"]
    r = await app_client.delete(f"/admin/tag-rules/{rid}", headers=admin_headers)
    assert r.status_code == 204
    lst = await app_client.get("/admin/tag-rules", headers=admin_headers)
    assert lst.json() == []


@pytest.mark.asyncio
async def test_delete_unknown_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.delete("/admin/tag-rules/nope", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reorder(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = (await _create(app_client, admin_headers, matcher_type="email_domain", pattern="a.edu", tag="aaa")).json()
    b = (await _create(app_client, admin_headers, matcher_type="always", tag="bbb")).json()
    r = await app_client.post(
        "/admin/tag-rules/reorder", headers=admin_headers, json={"order": [b["id"], a["id"]]}
    )
    assert r.status_code == 200
    assert [row["tag"] for row in r.json()] == ["bbb", "aaa"]


@pytest.mark.asyncio
async def test_reorder_mismatch_422(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    a = (await _create(app_client, admin_headers, matcher_type="always", tag="aaa")).json()
    r = await app_client.post(
        "/admin/tag-rules/reorder", headers=admin_headers, json={"order": [a["id"], "ghost"]}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_test_endpoint_dry_run(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _create(
        app_client, admin_headers,
        matcher_type="email_localpart_regex", pattern=r"[a-z]{0,2}\d{6,}", tag="student",
    )
    await _create(app_client, admin_headers, matcher_type="always", tag="teacher")

    r1 = await app_client.post("/admin/tag-rules/test", headers=admin_headers, json={"email": "b10901234@school.edu"})
    assert r1.status_code == 200
    assert r1.json()["matched"] is True
    assert r1.json()["tag"] == "student"

    r2 = await app_client.post("/admin/tag-rules/test", headers=admin_headers, json={"email": "prof.wang@school.edu"})
    assert r2.json()["tag"] == "teacher"
