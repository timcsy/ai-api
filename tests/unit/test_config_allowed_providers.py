"""Phase 5 T003: allowed_providers default covers the 4 first-batch providers."""
from __future__ import annotations

from ai_api.config import Settings


def test_default_allowed_providers_includes_four_providers() -> None:
    s = Settings()
    assert set(s.allowed_providers) >= {"azure", "openai", "anthropic", "gemini"}


def test_provider_key_enc_key_default_empty(monkeypatch) -> None:
    """Empty default; production must override via PROVIDER_KEY_ENC_KEY env / K8s Secret."""
    monkeypatch.delenv("PROVIDER_KEY_ENC_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.provider_key_enc_key == ""
