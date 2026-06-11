"""Phase 29 ③ (041) US1: contract tests for POST /v1/images/generations.

Image models (Azure gpt-image) are token-billed → reuse the token path (like
embeddings). Upstream litellm.aimage_generation is mocked.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import CallOutcome, CallRecord

IMG = "gpt-image-1"  # azure provider via env fallback (like embeddings tests)


async def _alloc(client: AsyncClient, admin_headers: dict[str, str], model: str = IMG) -> dict:
    r = await client.post(
        "/admin/allocations", headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": model},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub_image() -> dict:
    return {
        "created": 0,
        "data": [{"b64_json": "aGVsbG8="}],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


async def _last(outcome: CallOutcome) -> CallRecord | None:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(CallRecord).where(CallRecord.outcome == outcome)
            .order_by(CallRecord.started_at.desc())
        )).scalars().all()
        return rows[0] if rows else None


@pytest.mark.asyncio
async def test_images_200_billed(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aimage_generation", new=AsyncMock(return_value=_stub_image())):
        r = await app_client.post(
            "/v1/images/generations", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": IMG, "prompt": "a red dot"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["b64_json"] == "aGVsbG8="
    rec = await _last(CallOutcome.success)
    assert rec is not None and rec.prompt_tokens == 7 and rec.allocation_id == alloc["id"]


@pytest.mark.asyncio
async def test_images_400_missing_prompt(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/images/generations", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": IMG},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_images_401_no_token(app_client: AsyncClient) -> None:
    r = await app_client.post("/v1/images/generations", json={"model": IMG, "prompt": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_images_model_mismatch(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    r = await app_client.post(
        "/v1/images/generations", headers={"Authorization": f"Bearer {alloc['token']}"},
        json={"model": "other-model", "prompt": "x"},
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_images_upstream_error(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    alloc = await _alloc(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aimage_generation",
               new=AsyncMock(side_effect=RuntimeError("DeploymentNotFound"))):
        r = await app_client.post(
            "/v1/images/generations", headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": IMG, "prompt": "x"},
        )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "upstream_error"
    rec = await _last(CallOutcome.upstream_error)
    assert rec is not None and rec.allocation_id == alloc["id"]
