"""Phase 5 T054 / US4: env→DB migration CLI is idempotent + activates DB credential."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ai_api.cli.migrate_azure_env import _run
from ai_api.db import get_sessionmaker
from ai_api.models import ProviderCredential


def _stub() -> dict:
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "test",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migrate_creates_db_credential_then_idempotent(
    app_client: AsyncClient,
) -> None:
    """Run CLI twice — first creates 1 row, second skips with 'already migrated' message."""
    # First run
    rc = await _run()
    assert rc == 0

    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(
            select(ProviderCredential).where(ProviderCredential.provider == "azure")
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].label == "migrated-from-env"
        assert rows[0].fingerprint  # not empty

    # Second run — should not create another
    rc2 = await _run()
    assert rc2 == 0
    async with sm() as s:
        rows = (await s.execute(
            select(ProviderCredential).where(ProviderCredential.provider == "azure")
        )).scalars().all()
        assert len(rows) == 1  # still only 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_after_migration_proxy_uses_db_credential(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """After migration, proxy reads from DB (last_used_at populated)."""
    await _run()

    create = await app_client.post(
        "/admin/allocations",
        headers=admin_headers,
        json={"subject": "alice@example.com", "resource_model": "azure/gpt-4o-mini"},
    )
    alloc = create.json()

    captured: dict = {}

    async def fake(**kwargs):
        captured.update(kwargs)
        return _stub()

    with patch("litellm.acompletion", side_effect=fake):
        r = await app_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {alloc['token']}"},
            json={"model": "azure/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200
    # Should be the env-fallback key value (since that's what migration captured).
    # Whether it came from DB row or env doesn't matter for the value here, but the
    # last_used_at on the DB row confirms DB path:
    sm = get_sessionmaker()
    async with sm() as s:
        row = (await s.execute(
            select(ProviderCredential).where(ProviderCredential.provider == "azure")
        )).scalar_one()
        assert row.last_used_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migrate_with_no_env_returns_zero(
    app_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When AZURE_OPENAI_API_KEY is empty, CLI prints 'nothing to migrate' and exits 0."""
    from ai_api.config import get_settings
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        rc = await _run()
        assert rc == 0
    finally:
        get_settings.cache_clear()
