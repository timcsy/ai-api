"""Phase 5 T004: Fernet roundtrip + tamper rejection + key load failure."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from ai_api.services.crypto import CryptoConfigError, decrypt_str, encrypt_str, get_fernet


@pytest.fixture
def valid_key() -> str:
    return Fernet.generate_key().decode()


def test_encrypt_then_decrypt_roundtrip(monkeypatch: pytest.MonkeyPatch, valid_key: str) -> None:
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", valid_key)
    _reset_fernet_cache()
    plain = "sk-test-1234567890"
    enc = encrypt_str(plain)
    assert isinstance(enc, bytes)
    assert enc != plain.encode()
    assert decrypt_str(enc) == plain


def test_tampered_ciphertext_raises(monkeypatch: pytest.MonkeyPatch, valid_key: str) -> None:
    from cryptography.fernet import InvalidToken
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", valid_key)
    _reset_fernet_cache()
    enc = encrypt_str("hello")
    tampered = enc[:-1] + (b"X" if enc[-1:] != b"X" else b"Y")
    with pytest.raises(InvalidToken):
        decrypt_str(tampered)


def test_decrypt_with_wrong_key_raises(monkeypatch: pytest.MonkeyPatch, valid_key: str) -> None:
    from cryptography.fernet import InvalidToken
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", valid_key)
    _reset_fernet_cache()
    enc = encrypt_str("hello")

    other_key = Fernet.generate_key().decode()
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", other_key)
    _reset_fernet_cache()
    with pytest.raises(InvalidToken):
        decrypt_str(enc)


def test_missing_key_raises_crypto_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", "")
    _reset_fernet_cache()
    with pytest.raises(CryptoConfigError):
        get_fernet()


def test_invalid_key_format_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_KEY_ENC_KEY", "not-a-valid-fernet-key")
    _reset_fernet_cache()
    with pytest.raises(CryptoConfigError):
        get_fernet()


def _reset_fernet_cache() -> None:
    """Force settings + fernet cache rebuild between tests."""
    from ai_api.config import get_settings
    from ai_api.services import crypto

    get_settings.cache_clear()
    crypto._FERNET = None  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset_after_each() -> None:
    """Always restore caches after each test in this module so the next
    suite gets a fresh Settings reading the conftest-default env."""
    yield
    _reset_fernet_cache()
