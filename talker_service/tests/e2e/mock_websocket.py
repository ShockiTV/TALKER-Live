"""In-memory WebSocket for e2e testing — no TCP, no threads.

Implements the subset of Starlette's ``WebSocket`` interface used by
``WSRouter.websocket_endpoint()`` (accept, receive_text, send_text, close)
backed by a pair of ``asyncio.Queue`` objects.

LuaSimulator uses ``inject()`` / ``receive()`` to communicate through
this mock without any real network I/O.
"""

from __future__ import annotations

import asyncio

from fastapi import WebSocketDisconnect


class MockWebSocket:
    """Drop-in replacement for ``starlette.websockets.WebSocket`` in tests.

    Two queues bridge the WSRouter and LuaSimulator:
      * ``_incoming``  — messages the router will *receive*  (sim → router)
      * ``_outgoing``  — messages the router has *sent*      (router → sim)
    """

    def __init__(self) -> None:
        self._incoming: asyncio.Queue[str] = asyncio.Queue()
        self._outgoing: asyncio.Queue[str] = asyncio.Queue()
        self._closed = False
        # WSRouter reads this for token auth — empty means no token provided
        self.query_params: dict[str, str] = {}

    # ── Starlette WebSocket interface (used by WSRouter) ──────

    async def accept(self, subprotocol: str | None = None) -> None:  # noqa: ARG002
        """Accept the WebSocket connection (no-op for mock)."""

    async def receive_text(self) -> str:
        """Block until a message is available (sim → router direction).

        Raises ``WebSocketDisconnect`` when ``disconnect()`` has been called.
        """
        if self._closed:
            raise WebSocketDisconnect(code=1000)
        try:
            return await self._incoming.get()
        except asyncio.CancelledError:
            raise WebSocketDisconnect(code=1000) from None

    async def send_text(self, data: str) -> None:
        """Enqueue a message from the router for the simulator to pick up."""
        if not self._closed:
            await self._outgoing.put(data)

    async def close(self, code: int = 1000) -> None:  # noqa: ARG002
        """Mark the socket as closed."""
        self._closed = True

    # ── Helpers for LuaSimulator ──────────────────────────────

    async def inject(self, data: str) -> None:
        """Put a raw JSON string into the incoming queue (sim → router)."""
        await self._incoming.put(data)

    async def receive(self, timeout: float = 0.02) -> str | None:
        """Get a message sent by the router (router → sim).

        Returns ``None`` on timeout (no message available).
        """
        try:
            return await asyncio.wait_for(self._outgoing.get(), timeout)
        except asyncio.TimeoutError:
            return None

    def disconnect(self) -> None:
        """Signal the mock to raise ``WebSocketDisconnect`` on next receive."""
        self._closed = True
        # Wake up any blocked receive_text() call so it raises immediately
        self._incoming.put_nowait("")
