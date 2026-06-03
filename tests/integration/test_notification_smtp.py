"""Phase 13 US1 T015-T016: integration tests with aiosmtpd test server."""
from __future__ import annotations

import asyncio
from email import message_from_bytes
from email.message import Message
from typing import Any

import pytest
import pytest_asyncio
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message as AiosmtpdMessageHandler


class CapturingHandler(AiosmtpdMessageHandler):
    """Collects messages received by the in-process SMTP server."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[Message] = []

    def handle_message(self, message: Message) -> None:
        self.messages.append(message)


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture
async def smtp_server() -> Any:
    handler = CapturingHandler()
    port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield controller, handler
    finally:
        controller.stop()
        await asyncio.sleep(0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aiosmtpd_plaintext_round_trip(smtp_server: Any) -> None:
    """Smoke: aiosmtplib can deliver to aiosmtpd; we capture the raw bytes back."""
    controller, handler = smtp_server
    import aiosmtplib

    msg_bytes = (
        b"From: bot@example.com\r\n"
        b"To: tim@example.com\r\n"
        b"Subject: integration\r\n"
        b"\r\n"
        b"hello\r\n"
    )
    errors, response = await aiosmtplib.send(
        message_from_bytes(msg_bytes),
        hostname=controller.hostname,
        port=controller.port,
        start_tls=False,
        use_tls=False,
        timeout=15,
    )
    assert errors == {}
    assert response  # non-empty success message
    assert len(handler.messages) == 1
    assert "tim@example.com" in handler.messages[0]["To"]
    assert handler.messages[0]["Subject"] == "integration"
