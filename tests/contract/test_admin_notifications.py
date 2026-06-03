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
async def test_password_whitespace_stripped_and_fingerprint_from_plaintext(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Gmail App Password paste has spaces; they should be stripped on save, and
    the fingerprint should derive from plaintext (different pw -> different fp)."""
    from sqlalchemy import select

    from ai_api.db import get_sessionmaker
    from ai_api.models import NotificationConfig
    from ai_api.services.crypto import decrypt_str

    # Save with a Gmail-style spaced App Password
    cfg_spaced = {**_VALID_CONFIG, "smtp_password": "abcd efgh ijkl mnop"}
    r = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=cfg_spaced
    )
    assert r.status_code == 200, r.text
    fp_1 = r.json()["smtp_password_fingerprint"]

    # Stored plaintext has no spaces
    sm = get_sessionmaker()
    async with sm() as s:
        cfg = (await s.execute(select(NotificationConfig))).scalar_one()
        assert decrypt_str(cfg.smtp_password_encrypted) == "abcdefghijklmnop"

    # A different password yields a different fingerprint
    cfg_other = {**_VALID_CONFIG, "smtp_password": "totally-different-pw"}
    r2 = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=cfg_other
    )
    fp_2 = r2.json()["smtp_password_fingerprint"]
    assert fp_1 != fp_2
    # Fingerprint is NOT the constant Fernet-ciphertext prefix
    assert not fp_1.startswith("67414141")
    assert not fp_2.startswith("67414141")


@pytest.mark.asyncio
async def test_blank_password_keeps_existing_on_edit(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Editing other fields with a blank password keeps the stored password
    (FR: '留白＝沿用已儲存的密碼'). Previously this 400'd — the UI promised it
    but the backend required a non-empty password every save."""
    from sqlalchemy import select

    from ai_api.db import get_sessionmaker
    from ai_api.models import NotificationConfig, NotificationConfigStatus

    # First save with a real password
    r1 = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=_VALID_CONFIG
    )
    assert r1.status_code == 200, r1.text
    fp_before = r1.json()["smtp_password_fingerprint"]

    # Pretend a successful test verified the config
    sm = get_sessionmaker()
    async with sm() as s:
        cfg = (await s.execute(select(NotificationConfig))).scalar_one()
        cfg.status = NotificationConfigStatus.verified
        await s.commit()

    # Now change recipients only, leave password blank
    edit = {**_VALID_CONFIG, "recipients": ["new@example.com"], "smtp_password": ""}
    r2 = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=edit
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["recipients"] == ["new@example.com"]
    # Same password kept → same fingerprint
    assert body["smtp_password_fingerprint"] == fp_before
    # Recipient-only change does NOT invalidate verified status
    assert body["status"] == "verified"


@pytest.mark.asyncio
async def test_blank_password_on_first_setup_is_rejected(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """No existing config + blank password → must provide one."""
    payload = {**_VALID_CONFIG, "smtp_password": ""}
    r = await app_client.put(
        "/admin/notifications/config", headers=admin_headers, json=payload
    )
    assert r.status_code in (400, 422)


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


# ----- GET /admin/notifications/history (US5) -----

async def _seed_records(app_client: AsyncClient, admin_headers: dict[str, str], n: int) -> None:
    """Seed n notification records directly via the DB session."""
    from datetime import UTC, datetime, timedelta

    from ulid import ULID

    from ai_api.db import get_sessionmaker
    from ai_api.models import NotificationOutcome, NotificationRecord

    sm = get_sessionmaker()
    base = datetime.now(UTC)
    async with sm() as session:
        for i in range(n):
            session.add(
                NotificationRecord(
                    id=str(ULID()),
                    event_type="allocation_quarantined" if i % 2 == 0 else "responses_upstream_error_burst",
                    audit_event_id=None,
                    dedup_bucket_id=None,
                    outcome=NotificationOutcome.sent if i % 3 else NotificationOutcome.send_failed_auth,
                    recipients=["admin@example.com"],
                    per_recipient_status={"admin@example.com": "ok"},
                    subject=f"test {i}",
                    body_preview="body",
                    smtp_response_code=250,
                    error_message=None,
                    latency_ms=100,
                    created_at=base - timedelta(seconds=i),
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_list_history_returns_paginated_records(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_records(app_client, admin_headers, 60)
    r = await app_client.get("/admin/notifications/history?limit=20", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 20
    assert body["next_cursor"] is not None
    # second page
    r2 = await app_client.get(
        f"/admin/notifications/history?limit=20&cursor={body['next_cursor']}",
        headers=admin_headers,
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["rows"]) == 20
    # no overlap between pages
    ids1 = {row["id"] for row in body["rows"]}
    ids2 = {row["id"] for row in body2["rows"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_history_filters_by_event_type(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_records(app_client, admin_headers, 20)
    r = await app_client.get(
        "/admin/notifications/history?event_type=allocation_quarantined", headers=admin_headers
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert all(row["event_type"] == "allocation_quarantined" for row in rows)
    assert len(rows) > 0


@pytest.mark.asyncio
async def test_history_filters_by_outcome(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _seed_records(app_client, admin_headers, 20)
    r = await app_client.get(
        "/admin/notifications/history?outcome=send_failed_auth", headers=admin_headers
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert all(row["outcome"] == "send_failed_auth" for row in rows)


@pytest.mark.asyncio
async def test_primary_record_surfaces_bucket_count(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from datetime import UTC, datetime, timedelta

    from ulid import ULID

    from ai_api.db import get_sessionmaker
    from ai_api.models import NotificationDedupBucket, NotificationOutcome, NotificationRecord

    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as session:
        rec_id = str(ULID())
        bucket_id = str(ULID())
        session.add(
            NotificationRecord(
                id=rec_id, event_type="allocation_quarantined", audit_event_id=None,
                dedup_bucket_id=bucket_id, outcome=NotificationOutcome.sent,
                recipients=["a@b.com"], per_recipient_status={"a@b.com": "ok"},
                subject="primary", body_preview="b", smtp_response_code=250,
                error_message=None, latency_ms=10, created_at=now,
            )
        )
        session.add(
            NotificationDedupBucket(
                id=bucket_id, event_type="allocation_quarantined",
                window_start=now, window_end=now + timedelta(minutes=5),
                event_count=50, primary_record_id=rec_id, last_event_at=now,
            )
        )
        await session.commit()

    r = await app_client.get("/admin/notifications/history", headers=admin_headers)
    assert r.status_code == 200
    rows = r.json()["rows"]
    primary = next(row for row in rows if row["id"] == rec_id)
    assert primary["bucket_event_count"] == 50
