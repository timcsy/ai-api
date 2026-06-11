"""Phase 26: admin "test model" — POST /admin/catalog/models/{slug}/test dispatches
by model kind; result IS the response (never 5xx); billable kinds gated; audited."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, ModelCatalog


async def _seed(slug: str, *, mode: str | None = None, modality_input=None, modality_output=None) -> None:
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    sync = {"raw": {"mode": mode}} if mode is not None else None
    async with sm() as s:
        s.add(ModelCatalog(
            slug=slug, provider=slug.split("/", 1)[0], display_name=slug, family="x",
            description="", modality_input=modality_input or ["text"],
            modality_output=modality_output or ["text"],
            capabilities=["chat"], context_window=1024, cost_tier="low",
            recommended_for=[], tags=[], example_request={}, official_doc_url=None,
            status="active", deprecation_note=None, created_at=now, updated_at=now,
            default_access="open", allowed_tags=[], denied_tags=[],
            self_service_enabled=False, self_service_default_quota=None,
            litellm_sync=sync,
        ))
        await s.commit()


async def _provider(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await client.post(
        "/admin/providers", headers=admin_headers,
        json={"provider": "azure", "label": "test", "api_key": "az-test-12345678"},
    )
    assert r.status_code in (200, 201), r.text


async def _last_audit_event() -> str | None:
    from ai_api.models import AuthAuditLog
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(AuthAuditLog).order_by(AuthAuditLog.created_at.desc()))).scalars().all()
        return rows[0].event_type if rows else None


URL = "/admin/catalog/models/azure/gpt-5/test"


# ---------------- US1: chat ----------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_pass(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/gpt-5", mode="chat")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.acompletion", new=AsyncMock(return_value={"ok": 1})):
        r = await app_client.post(URL, headers=admin_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is True and b["kind"] == "chat" and "latency_ms" in b
    assert await _last_audit_event() == AuditEventType.model_tested.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_upstream_fail_no_5xx(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/gpt-5", mode="chat")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.acompletion", new=AsyncMock(side_effect=RuntimeError("DeploymentNotFound"))):
        r = await app_client.post(URL, headers=admin_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is False and b["kind"] == "chat" and b["error_type"] == "upstream_error"
    assert "DeploymentNotFound" in b["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_credential(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # anthropic has no env fallback (unlike azure), so no seeded credential → unavailable
    await _seed("anthropic/claude-3", mode="chat")
    r = await app_client.post("/admin/catalog/models/anthropic/claude-3/test", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["error_type"] == "provider_unavailable"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_404(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    r = await app_client.post("/admin/catalog/models/azure/ghost/test", headers=admin_headers)
    assert r.status_code == 404, r.text


# ---------------- US2: embedding ----------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_embedding_pass(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/embed", mode="embedding")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aembedding", new=AsyncMock(return_value={"data": []})) as m:
        r = await app_client.post("/admin/catalog/models/azure/embed/test", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["kind"] == "embedding"
    m.assert_awaited_once()


# ---------------- US3: billable (image / tts) ----------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_needs_confirmation_does_not_call(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/dalle", mode="image_generation")
    await _provider(app_client, admin_headers)
    img = AsyncMock(return_value={"data": []})
    with patch("ai_api.proxy.upstream.aimage_generation", new=img):
        r = await app_client.post("/admin/catalog/models/azure/dalle/test", headers=admin_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is False and b["kind"] == "image" and b["needs_confirmation"] is True
    img.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_confirmed_calls(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/dalle", mode="image_generation")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aimage_generation", new=AsyncMock(return_value={"data": []})) as m:
        r = await app_client.post(
            "/admin/catalog/models/azure/dalle/test", headers=admin_headers,
            json={"acknowledge_billable": True},
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["kind"] == "image"
    m.assert_awaited_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_confirmed_passes_voice(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/tts", mode="audio_speech")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aspeech", new=AsyncMock(return_value=b"audio")) as m:
        r = await app_client.post(
            "/admin/catalog/models/azure/tts/test", headers=admin_headers,
            json={"acknowledge_billable": True},
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["kind"] == "tts"
    assert m.call_args.kwargs.get("voice")


# ---------------- US4: binary/document kinds (billable real tests) ----------------
@pytest.mark.integration
@pytest.mark.asyncio
async def test_stt_confirmed_calls(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """STT now has a recipe (sends a minimal silent WAV) → billable real test."""
    await _seed("azure/whisper", mode="audio_transcription")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.atranscription", new=AsyncMock(return_value={"text": ""})) as m:
        # billable → no acknowledge means needs_confirmation, no upstream call
        r0 = await app_client.post("/admin/catalog/models/azure/whisper/test", headers=admin_headers)
        assert r0.json().get("needs_confirmation") is True and not m.await_count
        r = await app_client.post(
            "/admin/catalog/models/azure/whisper/test", headers=admin_headers,
            json={"acknowledge_billable": True},
        )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is True and b["kind"] == "stt" and "latency_ms" in b
    m.assert_awaited_once()
    assert m.call_args.kwargs.get("file")  # a (filename, bytes) fixture was sent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_edit_confirmed_calls(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await _seed("azure/img-edit", mode="image_edit")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aimage_edit", new=AsyncMock(return_value={"data": []})) as m:
        r = await app_client.post(
            "/admin/catalog/models/azure/img-edit/test", headers=admin_headers,
            json={"acknowledge_billable": True},
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["kind"] == "image_edit"
    m.assert_awaited_once()
    assert m.call_args.kwargs.get("image")  # a (filename, bytes) fixture was sent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_confirmed_calls(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """Search routes by search_provider (not model) → recipe remaps the slug."""
    await _seed("azure/web-search", mode="search")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.asearch", new=AsyncMock(return_value={"results": []})) as m:
        r = await app_client.post(
            "/admin/catalog/models/azure/web-search/test", headers=admin_headers,
            json={"acknowledge_billable": True},
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["kind"] == "search"
    m.assert_awaited_once()
    assert m.call_args.kwargs.get("search_provider") == "azure/web-search"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_mode_unsupported(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    # 'video_generation' is a genuinely-unknown mode for the admin test button
    # (moderation/rerank/etc. became known kinds in Phase 29③/31; only the not-yet-
    # supported modes — video/realtime/vector_store — remain 'unknown').
    await _seed("azure/video-x", mode="video_generation")
    await _provider(app_client, admin_headers)
    r = await app_client.post("/admin/catalog/models/azure/video-x/test", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "unknown" and r.json()["supported"] is False


# ---------------- Phase 31 follow-up: recipe table = single source of truth ----------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_ocr_confirmed_calls(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """The exact bug was: ocr had no test branch but is_supported said 'supported'
    → fake '通過 0ms'. Now ocr has a real recipe (sends a minimal PNG document) →
    billable real test, never a fake pass."""
    await _seed("azure/mistral-doc-ocr", mode="ocr")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.aocr", new=AsyncMock(return_value={"pages": []})) as m:
        # billable → needs acknowledgement before any upstream call
        r0 = await app_client.post("/admin/catalog/models/azure/mistral-doc-ocr/test", headers=admin_headers)
        assert r0.json().get("needs_confirmation") is True and not m.await_count
        r = await app_client.post(
            "/admin/catalog/models/azure/mistral-doc-ocr/test", headers=admin_headers,
            json={"acknowledge_billable": True},
        )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is True and b["kind"] == "ocr" and "latency_ms" in b
    m.assert_awaited_once()
    assert m.call_args.kwargs.get("document")  # a document fixture was sent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_moderation_real_test(app_client: AsyncClient, admin_headers: dict[str, str]) -> None:
    """A recipe was added for moderation → it now actually calls upstream (real test)."""
    await _seed("azure/text-moderation", mode="moderation")
    await _provider(app_client, admin_headers)
    with patch("ai_api.proxy.upstream.amoderation", new=AsyncMock(return_value={"ok": 1})) as mock:
        r = await app_client.post("/admin/catalog/models/azure/text-moderation/test", headers=admin_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ok"] is True and b["kind"] == "moderation" and "latency_ms" in b
    mock.assert_awaited_once()  # it really called upstream (not a 0ms no-op)
