"""LuaSimulator — simulates the Lua WebSocket client for e2e tests.

Uses a MockWebSocket (in-memory asyncio queues, same process as WSRouter).
No TCP ports, no OS socket permissions required.

Communication topology:
  LuaSimulator → MockWebSocket._incoming → WSRouter.receive_text()
  WSRouter.send_text() → MockWebSocket._outgoing → LuaSimulator.receive()

All messages use the JSON envelope format: ``{"t": topic, "p": payload, "ts": ms}``.
State query responses include the ``r`` field for request-id correlation.
"""

import asyncio
import json
import time
from typing import Any

from loguru import logger

from .mock_websocket import MockWebSocket


class LuaSimulator:
    """Simulates Lua's WebSocket client in-process for e2e tests.

    Sends JSON envelopes through the MockWebSocket and receives envelopes
    published by the service.  A background poll loop auto-responds to
    state.query.* topics using configured mocks and fires ``done_event``
    when ``dialogue.display`` arrives.
    """

    def __init__(
        self,
        mock_ws: MockWebSocket,
        state_mocks: dict[str, dict] | None = None,
    ):
        """
        Args:
            mock_ws: Shared MockWebSocket (same instance passed to WSRouter).
            state_mocks: Dict keyed by state.query topic (e.g. "state.query.memories")
                         mapping to {"response": {...}} — the data to return.
        """
        self._ws = mock_ws
        self._state_mocks: dict[str, dict] = state_mocks or {}

        # Records — structured objects, not raw wire strings
        self.published_to_service: list[dict] = []    # what we sent
        self.received_from_service: list[dict] = []   # what we received

        self.done_event: asyncio.Event = asyncio.Event()
        self._poll_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background poll loop."""
        self._poll_task = asyncio.create_task(self._poll_loop(), name="lua-sim-poll")

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a message to the service (Lua → Python direction).

        Serializes to JSON envelope ``{"t": topic, "p": payload, "ts": ms}``.
        """
        envelope = {
            "t": topic,
            "p": payload,
            "ts": int(time.time() * 1000),
        }
        await self._ws.inject(json.dumps(envelope))
        self.published_to_service.append({"topic": topic, "payload": payload})
        logger.debug(f"LuaSimulator → service: {topic}")

    async def _poll_loop(self) -> None:
        """Receive messages from the service and dispatch them."""
        while True:
            try:
                raw = await self._ws.receive(timeout=0.02)
                if raw is None:
                    # No message available — yield and retry
                    await asyncio.sleep(0)
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as exc:
                    logger.warning(f"LuaSimulator: JSON decode error: {exc}")
                    continue

                topic = data.get("t")
                if not topic:
                    logger.warning(f"LuaSimulator: envelope missing 't': {raw[:80]}")
                    continue

                payload = data.get("p", {})
                r = data.get("r")

                self.received_from_service.append({"topic": topic, "payload": payload})
                logger.debug(f"LuaSimulator ← service: {topic}")

                if topic == "state.query" or topic.startswith("state.query."):
                    await self._respond_to_state_query(topic, payload, r)

                if topic == "dialogue.display":
                    self.done_event.set()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"LuaSimulator poll error: {exc}")
                await asyncio.sleep(0.01)

    # Maps batch resource names to state_mocks topic keys
    _RESOURCE_TO_MOCK_TOPIC: dict[str, str] = {
        "store.memories": "state.query.memories",
        "store.events": "state.query.events",
        "query.character": "state.query.character",
        "query.world": "state.query.world",
        "query.characters_alive": "state.query",
        "query.characters_nearby": "state.query.nearby",
        # Tool-based conversation resources (ConversationManager)
        "memory.events": "state.query.events",
        "memory.summaries": "state.query.summaries",
        "memory.background": "state.query.background",
        "personality": "state.query.personality",
        "backstory": "state.query.backstory",
    }

    async def _respond_to_state_query(
        self, topic: str, payload: dict[str, Any], r: str | None
    ) -> None:
        """Auto-respond to a state.query.* message using configured mocks.

        The ``r`` field from the incoming envelope is echoed back so
        ``WSRouter`` can resolve the pending future.
        """
        request_id = payload.get("request_id") or r
        if not request_id:
            logger.warning(f"LuaSimulator: state query with no request_id on {topic}")
            return

        # Handle batch queries by routing sub-queries to individual mocks
        if topic == "state.query.batch":
            await self._respond_to_batch_query(request_id, payload)
            return

        mock = self._state_mocks.get(topic)
        if mock is None:
            logger.warning(f"LuaSimulator: no mock configured for {topic}")
            return

        response_payload = {
            "request_id": request_id,
            "data": mock.get("response", {}),
        }
        envelope = {
            "t": "state.response",
            "p": response_payload,
            "r": request_id,
            "ts": int(time.time() * 1000),
        }
        await self._ws.inject(json.dumps(envelope))
        logger.debug(f"LuaSimulator: responded to {topic} (request_id={request_id})")

    async def _respond_to_batch_query(
        self, request_id: str, payload: dict[str, Any]
    ) -> None:
        """Respond to state.query.batch by routing sub-queries to individual mocks."""
        queries = payload.get("queries", [])
        results: dict[str, dict[str, Any]] = {}

        for q in queries:
            qid = q["id"]
            resource = q["resource"]
            mock_topic = self._RESOURCE_TO_MOCK_TOPIC.get(resource)
            if mock_topic is None:
                results[qid] = {"ok": False, "error": f"unknown resource: {resource}"}
                continue
            mock = self._state_mocks.get(mock_topic)
            if mock is None:
                results[qid] = {"ok": False, "error": f"no mock for {mock_topic}"}
                continue
            results[qid] = {"ok": True, "data": mock.get("response", {})}

        response_payload = {
            "request_id": request_id,
            "data": {"results": results},
        }
        envelope = {
            "t": "state.response",
            "p": response_payload,
            "r": request_id,
            "ts": int(time.time() * 1000),
        }
        await self._ws.inject(json.dumps(envelope))
        logger.debug(
            f"LuaSimulator: responded to batch query ({len(queries)} sub-queries, "
            f"request_id={request_id})"
        )

    def close(self) -> None:
        """Cancel poll task. Does NOT close the MockWebSocket."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
