"""Top-level pytest configuration."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest_asyncio

# Ensure src/ is on path even if package not installed in editable mode.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Provide deterministic defaults for tests if env not set.
os.environ.setdefault("ADMIN_BOOTSTRAP_TOKEN", "test-admin-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AZURE_OPENAI_API_BASE", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-azure-key-DO-NOT-LEAK")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-06-01")
os.environ.setdefault("AZURE_OPENAI_TEST_MODEL", "gpt-test")
# Phase 5: deterministic Fernet key for ProviderCredential encryption tests.
os.environ.setdefault(
    "PROVIDER_KEY_ENC_KEY", "wG4iqV3qxGqQfp_8ARDqVU93G8YzxBOFnHTL98_3l9I="
)


@pytest_asyncio.fixture
async def make_provider_credential():
    """Phase 5: helper to inject a ProviderCredential row for tests. Shared
    across contract/integration to avoid duplication."""
    from ai_api.db import get_sessionmaker
    from ai_api.services.provider_credentials import ProviderCredentialService

    sm = get_sessionmaker()

    async def _make(
        *,
        provider: str,
        label: str = "test",
        api_key: str = "test-key-1234",
        base_url: str | None = None,
        extra_config: dict | None = None,
    ):
        async with sm() as s:
            cred = await ProviderCredentialService(s).create(
                provider=provider,
                label=label,
                api_key=api_key,
                base_url=base_url,
                extra_config=extra_config,
            )
            await s.commit()
            return cred

    return _make
