"""Phase 13 US1: contract tests for /admin/notifications/*.

Spec contract: specs/022-admin-email-notifications/contracts/admin-notifications.openapi.yaml
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

_VALID_CONFIG = {
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_username": "bot@example.com",
    "smtp_password": "super-secret-app-password",
    "sender_email": "bot@example.com",
    "sender_name": "AI API Manager Test",
    "recipients": ["admin@example.com", "ops@example.com"],
}


# ----- GET /admin/notifications/config -----

@pytest.mark.asyncio
async def test_get_config_returns_204_when_unset(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.get("/admin/notifications/config", headers=admin_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_get_config_unauthenticated_returns_401_or_403(
    app_client: AsyncClient,
) -> None:
    r = await app_client.get("/admin/notifications/config")
    assert r.status_code in (401, 403)


# ----- PUT /admin/notifications/config -----

@pytest.mark.asyncio
async def test_put_config_persists_and_returns_masked(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=_VALID_CONFIG
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["smtp_host"] == "smtp.example.com"
    assert body["smtp_port"] == 587
    assert body["smtp_username"] == "bot@example.com"
    assert body["recipients"] == ["admin@example.com", "ops@example.com"]
    assert "smtp_password" not in body  # never echo plaintext
    assert "smtp_password_encrypted" not in body  # never echo raw ciphertext
    assert len(body["smtp_password_fingerprint"]) >= 4  # mask present
    assert body["status"] == "pending_test"
    assert body["enabled"] is True

    # Reload — settings persist, password still masked
    r2 = await app_client.get("/admin/notifications/config", headers=admin_headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["smtp_host"] == body["smtp_host"]
    assert "smtp_password" not in body2


@pytest.mark.asyncio
async def test_put_config_rejects_invalid_port(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    bad = {**_VALID_CONFIG, "smtp_port": 70000}
    r = await app_client.put("/admin/notifications/config", headers=admin_headers, json=bad)
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_put_config_rejects_malformed_recipients(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    bad = {**_VALID_CONFIG, "recipients": ["not-an-email"]}
    r = await app_client.put("/admin/notifications/config", headers=admin_headers, json=bad)
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_put_config_rejects_empty_smtp_host(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    bad = {**_VALID_CONFIG, "smtp_host": ""}
    r = await app_client.put("/admin/notifications/config", headers=admin_headers, json=bad)
    assert r.status_code in (400, 422)


# ----- DELETE /admin/notifications/config -----

@pytest.mark.asyncio
async def test_delete_config_clears_state(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Save first
    save = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=_VALID_CONFIG
    )
    assert save.status_code == 200

    # Delete
    d = await app_client.delete("/admin/notifications/config", headers=admin_headers)
    assert d.status_code == 204

    # GET now 204 again
    g = await app_client.get("/admin/notifications/config", headers=admin_headers)
    assert g.status_code == 204


# ----- POST /admin/notifications/test-send -----

@pytest.mark.asyncio
async def test_test_send_with_one_off_recipient(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """FR-007: test send uses a one-off recipient, NOT the saved recipient list."""
    # Save valid config
    await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=_VALID_CONFIG
    )
    # Mock aiosmtplib.send so we don't need a real SMTP server in this test
    from ai_api.services import notifier_email
    # aiosmtplib.send returns (errors_dict, response_str); empty dict = success
    with patch.object(notifier_email, "_smtp_send", new=AsyncMock(return_value=({}, "250 OK"))):
        r = await app_client.post(
            "/admin/notifications/test-send",
            headers=admin_headers,
            json={"test_recipient": "tim@example.com"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "success"
    assert "tim@example.com" in body["message"] or "已寄出" in body["message"]
    assert body["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_test_send_with_no_config_returns_400(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await app_client.post(
        "/admin/notifications/test-send",
        headers=admin_headers,
        json={"test_recipient": "tim@example.com"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_test_send_returns_actionable_error_on_auth_failure(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """FR-008: actionable error message with smtp_response_code."""
    await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=_VALID_CONFIG
    )
    import aiosmtplib

    from ai_api.services import notifier_email
    # Simulate auth failure from SMTP server
    with patch.object(
        notifier_email,
        "_smtp_send",
        new=AsyncMock(
            side_effect=aiosmtplib.SMTPAuthenticationError(535, "authentication failed")
        ),
    ):
        r = await app_client.post(
            "/admin/notifications/test-send",
            headers=admin_headers,
            json={"test_recipient": "tim@example.com"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "send_failed_auth"
    assert body["smtp_response_code"] == 535
    assert "authentication" in body["message"].lower() or "驗證" in body["message"]
