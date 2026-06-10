"""Phase 19 US2/US3 — install-script endpoints contract.

The dashboard's one-line install command points at these endpoints. The returned
script must carry the platform base_url, configure the custom `ccsh` provider
(Responses wire api, platform auth, no websockets), use device-flow + auth.json
(no env var), and write config merge-style so a /model switch does not decouple
(no readonly / wrapper).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from ai_api.config import get_settings


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/install/codex.sh", "/install/codex.ps1"])
async def test_install_script_served_with_required_config(
    app_client: AsyncClient, path: str
) -> None:
    r = await app_client.get(path)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert len(body) > 200

    # Points at the platform + custom provider (US2/US3).
    assert get_settings().base_url.rstrip("/") in body  # injected base_url
    assert "model_providers.ccsh" in body
    assert 'wire_api = "responses"' in body
    assert "requires_openai_auth = true" in body
    # device-flow + no env var.
    assert "/device/authorize" in body
    assert "/device/token" in body
    assert "codex login --with-api-key" in body
    # Pins Codex's default model from the device-flow response (else Codex uses
    # its own built-in default model instead of the one the key grants). The
    # literal differs per shell (sh writes model = "..."; ps1 uses backtick
    # quotes), so match the common "model = " prefix.
    assert "model = " in body


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/install/codex.sh", "/install/codex.ps1"])
async def test_install_script_failsoft_when_cli_unavailable(
    app_client: AsyncClient, path: str
) -> None:
    """A Codex CLI install failure (network / AV / unsupported OS) must NOT
    hard-abort before the device-flow. The script tracks CLI availability in a
    flag and, when the CLI is missing, still writes config + mints a key and
    hands it over for a manual finish — so the member isn't left with nothing."""
    body = (await app_client.get(path)).text
    flag = "CODEX_CLI" if path.endswith(".sh") else "CodexCli"
    assert flag in body  # CLI presence is tracked, not assumed to be exit-on-fail
    # The degraded branch surfaces the key + how to finish (provider already set).
    assert "金鑰" in body
    assert "codex login --with-api-key" in body  # the manual-finish hint survives


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/install/codex.sh", "/install/codex.ps1"])
async def test_install_script_no_decouple_strategy(app_client: AsyncClient, path: str) -> None:
    """US3: merge-style default provider + websockets off; never readonly/wrapper."""
    body = (await app_client.get(path)).text
    assert 'model_provider = "ccsh"' in body  # default provider survives /model switch
    assert "supports_websockets = false" in body
    # Must NOT rely on read-only config or a wrapper/alias.
    low = body.lower()
    assert "chmod a-w" not in low
    assert "readonly" not in low
    assert "alias codex" not in low
