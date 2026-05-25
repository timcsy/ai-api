"""Phase 5 T006: app refuses to start when PROVIDER_KEY_ENC_KEY missing/invalid.

SC-006: pod refuses to start with clear error, not "half-started" runtime crash.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from ai_api.config import get_settings
from ai_api.services import crypto
from ai_api.services.crypto import CryptoConfigError


@pytest.fixture
def crypto_isolation() -> Iterator[None]:
    """Clear settings + fernet cache before AND after, so test contamination doesn't
    leak a bad PROVIDER_KEY_ENC_KEY into subsequent tests."""
    get_settings.cache_clear()
    crypto._FERNET = None  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()
    crypto._FERNET = None  # type: ignore[attr-defined]


@pytest.mark.integration
def test_create_app_raises_when_key_missing(
    monkeypatch: pytest.MonkeyPatch, crypto_isolation: None
) -> None:
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", "")
    from ai_api.main import create_app

    with pytest.raises(CryptoConfigError, match="PROVIDER_KEY_ENC_KEY is not set"):
        create_app()


@pytest.mark.integration
def test_create_app_raises_when_key_malformed(
    monkeypatch: pytest.MonkeyPatch, crypto_isolation: None
) -> None:
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", "garbage-not-fernet")
    from ai_api.main import create_app

    with pytest.raises(CryptoConfigError, match="malformed"):
        create_app()
