"""Phase 017 US2: startup fail-fast on a default/empty ADMIN_BOOTSTRAP_TOKEN.

Mirrors the Fernet-key startup guard (test_startup_crypto.py): production
(COOKIE_SECURE=true) must refuse to start with the well-known default token,
while dev (COOKIE_SECURE=false) keeps the zero-config default usable.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from ai_api.config import DEFAULT_ADMIN_BOOTSTRAP_TOKEN, get_settings


@pytest.fixture
def settings_isolation() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_env(monkeypatch: pytest.MonkeyPatch, *, cookie_secure: bool, token: str) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "true" if cookie_secure else "false")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_TOKEN", token)
    # Provide a valid Fernet key so we isolate the token guard, not the crypto one.
    monkeypatch.setenv(
        "PROVIDER_KEY_ENC_KEY", "wG4iqV3qxGqQfp_8ARDqVU93G8YzxBOFnHTL98_3l9I="
    )


@pytest.mark.integration
def test_refuses_default_token_in_production(
    monkeypatch: pytest.MonkeyPatch, settings_isolation: None
) -> None:
    _set_env(monkeypatch, cookie_secure=True, token=DEFAULT_ADMIN_BOOTSTRAP_TOKEN)
    from ai_api.main import create_app

    with pytest.raises(RuntimeError, match="ADMIN_BOOTSTRAP_TOKEN"):
        create_app()


@pytest.mark.integration
def test_refuses_empty_token_in_production(
    monkeypatch: pytest.MonkeyPatch, settings_isolation: None
) -> None:
    _set_env(monkeypatch, cookie_secure=True, token="")
    from ai_api.main import create_app

    with pytest.raises(RuntimeError, match="ADMIN_BOOTSTRAP_TOKEN"):
        create_app()


@pytest.mark.integration
def test_allows_custom_token_in_production(
    monkeypatch: pytest.MonkeyPatch, settings_isolation: None
) -> None:
    _set_env(monkeypatch, cookie_secure=True, token="a-strong-random-secret-value")
    from ai_api.main import create_app

    create_app()  # must not raise


@pytest.mark.integration
def test_allows_default_token_in_dev(
    monkeypatch: pytest.MonkeyPatch, settings_isolation: None
) -> None:
    _set_env(monkeypatch, cookie_secure=False, token=DEFAULT_ADMIN_BOOTSTRAP_TOKEN)
    from ai_api.main import create_app

    create_app()  # dev keeps zero-config default


@pytest.mark.integration
def test_guard_message_does_not_leak_token_value(
    monkeypatch: pytest.MonkeyPatch, settings_isolation: None
) -> None:
    _set_env(monkeypatch, cookie_secure=True, token=DEFAULT_ADMIN_BOOTSTRAP_TOKEN)
    from ai_api.main import create_app

    with pytest.raises(RuntimeError) as exc:
        create_app()
    msg = str(exc.value)
    assert DEFAULT_ADMIN_BOOTSTRAP_TOKEN not in msg
    assert "production" in msg.lower() or "COOKIE_SECURE" in msg
