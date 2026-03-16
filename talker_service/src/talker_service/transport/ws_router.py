"""WebSocket message router — FastAPI WebSocket endpoint.

Accepts WebSocket connections at ``/ws``, parses JSON envelopes
(``{t, p, r, ts}``), routes to registered handlers, and supports
request/response correlation via the ``r`` field.

Optionally validates connections using ``TALKER_TOKENS`` env var.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Callable, Awaitable

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from starlette.websockets import WebSocketState

from .session import DEFAULT_SESSION

# Type alias for handler functions — handlers receive (payload, session_id, req_id)
MessageHandler = Callable[[dict[str, Any], str, int], Awaitable[None]]

# Monotonic request counter — assigned in _process_message for lifecycle tracing
_req_counter: int = 0


def parse_tokens(raw: str | None) -> dict[str, str]:
    """Parse ``TALKER_TOKENS`` env var into a name→token dict.

    Format: ``name:token,name2:token2,...``
    Malformed entries (no ``:``) are logged and skipped.
    Returns empty dict when *raw* is ``None`` or blank.
    """
    if not raw or not raw.strip():
        return {}

    tokens: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            logger.warning("Skipping malformed TALKER_TOKENS entry (no ':')")
            continue
        name, _, token = entry.partition(":")
        name = name.strip()
        token = token.strip()
        if name and token:
            tokens[name] = token
        else:
            logger.warning("Skipping malformed TALKER_TOKENS entry (empty name or token)")
    return tokens


class WSRouter:
    """Routes WebSocket messages to registered handlers based on topic.

    Manages multiple concurrent clients, envelope parsing,
    ``r``-field request/response correlation, and token auth.
    """

    def __init__(self, tokens: dict[str, str] | None = None) -> None:
        """Initialise.

        Args:
            tokens: Pre-parsed name→token map.  If *None*, reads
                    ``TALKER_TOKENS`` from environment.  Pass an empty dict
                    to explicitly disable auth.
        """
        if tokens is None:
            tokens = parse_tokens(os.environ.get("TALKER_TOKENS"))
        self._tokens = tokens
        self._auth_enabled = bool(tokens)

        self.handlers: dict[str, MessageHandler] = {}
        self._connections: list[WebSocket] = []
        self._conn_to_session: dict[WebSocket, str] = {}
        self._pending_requests: dict[str, asyncio.Future] = {}
        self.is_connected: bool = False
        self._session_registry = None  # set via set_session_registry()

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def on(self, topic: str, handler: MessageHandler) -> None:
        """Register *handler* for *topic*.

        Uses the ``on(topic, fn)`` signature for wiring in ``__main__.py``.
        """
        self.handlers[topic] = handler
        logger.debug(f"Registered handler for topic: {topic}")

    register_handler = on  # alias used by the spec

    def set_session_registry(self, registry) -> None:
        """Inject :class:`SessionRegistry` for session→connection and outbox."""
        self._session_registry = registry

    # ------------------------------------------------------------------
    # Request/response helpers
    # ------------------------------------------------------------------

    def create_request(self, request_id: str, timeout: float = 30.0) -> asyncio.Future:
        """Create a pending request future keyed by *request_id*.

        The future is resolved when a frame with matching ``r`` arrives.
        A timeout task cancels it if no response appears.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_requests[request_id] = future

        async def _timeout():
            await asyncio.sleep(timeout)
            if request_id in self._pending_requests:
                fut = self._pending_requests.pop(request_id)
                if not fut.done():
                    fut.set_exception(
                        TimeoutError(f"Request {request_id} timed out")
                    )

        asyncio.create_task(_timeout())
        return future

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        r: str | None = None,
        session: str | None = None,
    ) -> bool:
        """Send an envelope to connected clients.

        When *session* is provided, the message is sent only to that
        session's connection.  If the session has no active connection
        the message is buffered in its outbox (when a
        :class:`SessionRegistry` is available).

        When *session* is ``None``, the message is broadcast to **all**
        connected clients (backward-compatible default).

        Returns ``True`` if sent (or buffered) successfully.
        """
        envelope: dict[str, Any] = {
            "t": topic,
            "p": payload,
            "ts": int(time.time() * 1000),
        }
        if r is not None:
            envelope["r"] = r
        raw = json.dumps(envelope)

        sent = False

        if session is not None:
            # ── Targeted send ─────────────────────────────────────
            target_ws: WebSocket | None = None
            if self._session_registry:
                ctx = self._session_registry.get_session(session)
                target_ws = ctx.connection
            else:
                # Fallback: reverse-lookup without registry
                for ws, sid in self._conn_to_session.items():
                    if sid == session:
                        target_ws = ws
                        break

            if target_ws is not None:
                try:
                    await target_ws.send_text(raw)
                    sent = True
                except Exception:
                    self._remove_connection(target_ws)
            else:
                # Buffer in outbox if registry available
                if self._session_registry:
                    ctx = self._session_registry.get_session(session)
                    ctx.outbox.append(raw)
                    sent = True  # message accepted (buffered)
                    logger.debug(f"Buffered message for disconnected session {session}")
        else:
            # ── Broadcast ──────────────────────────────────────────
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(raw)
                    sent = True
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self._remove_connection(ws)

            if not sent and self._connections:
                logger.warning("publish: failed to send to any client")

        from ..config import settings  # deferred to avoid circular import
        if topic != "service.heartbeat.ack" or getattr(settings, "log_heartbeat", False):
            logger.debug(f"Published to {topic}")
        return sent

    # ------------------------------------------------------------------
    # WebSocket endpoint
    # ------------------------------------------------------------------

    async def websocket_endpoint(self, ws: WebSocket) -> None:
        """FastAPI WebSocket handler — intended to be mounted as ``/ws``."""

        # ── Auth ──────────────────────────────────────────────────────
        session_id = DEFAULT_SESSION
        _headers = getattr(ws, "headers", {})
        player_id = _headers.get("x-player-id", "local")
        branch = _headers.get("x-branch", "main")
        if self._auth_enabled:
            token = ws.query_params.get("token")
            if not token or token not in self._tokens.values():
                await ws.close(code=4001)
                logger.warning("WS connection rejected: invalid or missing token")
                return
            # Resolve session_id from token name
            for name, tok in self._tokens.items():
                if tok == token:
                    session_id = name
                    break

        await ws.accept()
        self._connections.append(ws)
        self._conn_to_session[ws] = session_id

        # Register connection in session registry (if available)
        if self._session_registry:
            ctx = self._session_registry.get_session(session_id)
            ctx.connection = ws
            ctx.player_id = player_id
            ctx.branch = branch

        self.is_connected = True
        logger.info(
            "WS client connected (session={}, player_id={}, branch={}, {} total)",
            session_id,
            player_id,
            branch,
            len(self._connections),
        )

        try:
            while True:
                raw = await ws.receive_text()
                await self._process_message(raw, ws)
        except WebSocketDisconnect:
            logger.info("WS client disconnected (session={})", session_id)
        except Exception as exc:
            logger.error(f"WS receive error: {exc}")
        finally:
            self._remove_connection(ws)

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _process_message(self, raw: str, ws: WebSocket | None = None) -> None:
        """Parse a JSON envelope and dispatch."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Malformed WS frame (invalid JSON)")
            return

        if not isinstance(data, dict):
            logger.warning("Malformed WS frame (not an object)")
            return

        topic: str | None = data.get("t")
        if not topic:
            logger.warning("Malformed WS frame (missing 't' field)")
            return

        payload: dict = data.get("p", {})
        r: str | None = data.get("r")

        # ── r-field short-circuit ─────────────────────────────────────
        if r and r in self._pending_requests:
            future = self._pending_requests.pop(r)
            if not future.done():
                if isinstance(payload, dict) and "error" in payload:
                    future.set_exception(Exception(payload["error"]))
                else:
                    future.set_result(payload)
            return

        if r and r not in self._pending_requests:
            # r-field present but no pending future — log and discard
            logger.warning(f"No pending request for r={r}, discarding")
            return

        # ── Resolve session_id from connection ────────────────────────
        session_id = self._conn_to_session.get(ws, DEFAULT_SESSION) if ws else DEFAULT_SESSION

        if ws and self._session_registry and isinstance(payload, dict):
            ctx = self._session_registry.get_session(session_id)
            payload = {
                **payload,
                "_connection": {
                    "player_id": ctx.player_id,
                    "branch": ctx.branch,
                    "game_session_id": ctx.game_session_id,
                },
            }

        # ── Assign monotonic req_id ───────────────────────────────────
        global _req_counter
        _req_counter += 1
        req_id = _req_counter

        # ── Handler dispatch ──────────────────────────────────────────
        handler = self.handlers.get(topic)
        if handler:
            logger.debug(f"[R:{req_id}] Dispatching {topic}")
            asyncio.create_task(handler(payload, session_id, req_id))
        else:
            if not topic.startswith("mic."):
                logger.warning(f"No handler for topic: {topic}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Close all active connections and cancel pending requests."""
        logger.info("Shutting down WSRouter...")
        self.is_connected = False

        for request_id, future in self._pending_requests.items():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

        for ws in list(self._connections):
            try:
                await ws.close(code=1001)
            except Exception:
                pass
        self._connections.clear()
        logger.info("WSRouter shutdown complete")

    # alias used by __main__.py
    shutdown = stop

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_connection(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        session_id = self._conn_to_session.pop(ws, None)

        # Clear connection on session context (keep session for outbox)
        if session_id and self._session_registry:
            ctx = self._session_registry.get_session(session_id)
            if ctx.connection is ws:
                ctx.connection = None

        self.is_connected = bool(self._connections)
        logger.debug("WS client removed ({} remaining)", len(self._connections))
