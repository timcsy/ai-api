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
