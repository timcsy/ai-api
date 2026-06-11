"""Phase 29 (038) US3: member catalog exposes derived `kind` so the UI can show
the right 'how to call' example (embedding → /v1/embeddings, chat → /v1/chat)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog


async def _login(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await client.post(
        "/admin/members", headers=admin_headers,
        json={"email": "k@x.com", "provider": "local_password",
              "initial_password": "VerySafePass123", "send_invitation": False},
    )
    r = await client.post("/auth/local/login",
                          json={"email": "k@x.com", "password": "VerySafePass123"})
    assert r.status_code == 200


async def _seed(slug: str, *, mode: str | None = None) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    sync = {"raw": {"mode": mode}} if mode is not None else None
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name=slug, family="x",
            description="", modality_input=["text"], modality_output=["text"],
            capabilities=["chat"], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None, litellm_sync=sync,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_catalog_detail_kind_embedding_vs_chat(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # credential gate: azure provider needs an active credential for its models to show
    from ai_api.services.provider_credentials import ProviderCredentialService
    sm = get_sessionmaker()
    async with sm() as s:
        await ProviderCredentialService(s).create(provider="azure", label="t", api_key="azure-test-key-1")
        await s.commit()
    await _seed("azure/text-embedding-3", mode="embedding")
    await _seed("azure/gpt-x", mode="chat")
    await _seed("azure/mistral-document-ai", mode="ocr")
    await _seed("azure/cohere-rerank", mode="rerank")
    await _login(app_client, admin_headers)

    emb = (await app_client.get("/catalog/models/azure/text-embedding-3")).json()
    chat = (await app_client.get("/catalog/models/azure/gpt-x")).json()
    ocr = (await app_client.get("/catalog/models/azure/mistral-document-ai")).json()
    rr = (await app_client.get("/catalog/models/azure/cohere-rerank")).json()
    assert emb["kind"] == "embedding"
    assert chat["kind"] == "chat"
    assert ocr["kind"] == "ocr"
    assert rr["kind"] == "rerank"

    # Phase 29 ③: admin model list also carries kind (for the "類型" display)
    admin_rows = (await app_client.get("/admin/catalog/models", headers=admin_headers)).json()
    by_slug = {r["slug"]: r for r in admin_rows}
    assert by_slug["azure/mistral-document-ai"]["kind"] == "ocr"
    assert by_slug["azure/cohere-rerank"]["kind"] == "rerank"
