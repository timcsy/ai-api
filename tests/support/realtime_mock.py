"""Phase 32 (043) T002: reusable fake realtime WS pair for CI.

The engine is bound to the test event loop, so a separate TestClient portal would
break asyncpg/aiosqlite. Instead the relay is driven in-loop by calling
`handle_realtime`/`run_relay` directly with these fakes — a mock *provider* realtime
WS plus a mock client WS — exactly the Constitution-Deviation remedy in the plan
(CI never touches a real Azure realtime WS; that is the maintainer's T027 smoke).
"""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Iterable
from typing import Any


class FakeDisconnect(Exception):
    """Mimics starlette WebSocketDisconnect from the client side."""


class FakeClosed(Exception):
    """Mimics websockets ConnectionClosed from the upstream side."""


class FakeClientWS:
    """Stands in for a FastAPI WebSocket (ClientWS interface).

    `inbound` is the scripted sequence of client→platform frames. After they are
    drained, `receive_text` either blocks (hold_open=True, simulating a still-open
    client until the platform closes) or raises FakeDisconnect (client ended/aborted).
    """

    def __init__(
        self,
        headers: dict[str, str],
        inbound: Iterable[str],
        *,
        hold_open: bool = False,
    ) -> None:
        self.headers = dict(headers)
        self._inbound: deque[str] = deque(inbound)
        self._hold = hold_open
        self.sent: list[str] = []          # platform→client frames (e.g. deltas)
        self.closed: tuple[int, str | None] | None = None
        self.accepted = False
        self._released = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if self._inbound:
            return self._inbound.popleft()
        if self._hold:
            await self._released.wait()
        raise FakeDisconnect()

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        if self.closed is None:
            self.closed = (code, reason)
        self._released.set()


class FakeUpstreamWS:
    """Stands in for the upstream provider realtime WS (UpstreamWS interface).

    `events` is the scripted sequence of provider→platform frames (delta/completed).
    After they drain, `recv` either raises FakeClosed (provider hung up) or blocks
    (close_after=False, stays open until the platform closes it).
    """

    def __init__(self, events: Iterable[str] | None = None, *, close_after: bool = False) -> None:
        self._events: deque[str] = deque(events or [])
        self._close_after = close_after
        self.sent: list[str] = []          # client→upstream forwarded frames
        self.closed = False
        self._released = asyncio.Event()

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if self._events:
            return self._events.popleft()
        if self._close_after:
            raise FakeClosed()
        await self._released.wait()
        raise FakeClosed()

    async def close(self) -> None:
        self.closed = True
        self._released.set()


def fake_opener(upstream: FakeUpstreamWS) -> Any:
    """Return an `open_upstream` callable that yields the given fake upstream and
    records the credential kwargs it was called with (to assert no-leak / routing)."""
    calls: list[dict[str, Any]] = []

    async def _open(**kwargs: Any) -> FakeUpstreamWS:
        calls.append(kwargs)
        return upstream

    _open.calls = calls  # type: ignore[attr-defined]
    return _open
