"""LuaSimulator — simulates the Lua ZMQ bridge for e2e tests.

Uses inproc:// transport (same zmq.asyncio.Context as ZMQRouter).
No TCP ports, no OS socket permissions required.

Socket topology (from Lua's perspective):
  LuaSimulator.PUB  binds   inproc://lua-to-python  ← ZMQRouter.SUB connects here
  LuaSimulator.SUB  connects inproc://python-to-lua  ← ZMQRouter.PUB binds here

Bind order: LuaSimulator must be created BEFORE ZMQRouter.run() is called so
the inproc://lua-to-python endpoint exists before the router connects to it.
With pyzmq>=25 (libzmq 4.x) connect-before-bind is also supported for inproc,
but explicit ordering avoids any edge cases.
"""

import asyncio
import json
from typing import Any

import zmq
import zmq.asyncio
from loguru import logger


class LuaSimulator:
    """Simulates Lua's ZMQ bridge in-process for e2e tests.

    Binds the PUB socket (lua-to-python direction) and connects the SUB socket
    (python-to-lua direction).  A background poll loop receives messages from
    the service, auto-responds to state.query.* topics using configured mocks,
    and fires done_event when dialogue.display arrives.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        state_mocks: dict[str, dict] | None = None,
    ):
        """
        Args:
            context: Shared ZMQ context (must be the same instance as ZMQRouter's).
            state_mocks: Dict keyed by state.query topic (e.g. "state.query.memories")
                         mapping to {"response": {...}} — the data to return.
        """
        self._ctx = context
        self._state_mocks: dict[str, dict] = state_mocks or {}

        # PUB: we publish events TO Python (lua-to-python direction)
        self._pub: zmq.asyncio.Socket = context.socket(zmq.PUB)
        self._pub.setsockopt(zmq.LINGER, 0)
        self._pub.bind("inproc://lua-to-python")

        # SUB: we receive commands FROM Python (python-to-lua direction)
        self._sub: zmq.asyncio.Socket = context.socket(zmq.SUB)
        self._sub.setsockopt(zmq.LINGER, 0)
        self._sub.setsockopt(zmq.RCVTIMEO, 20)  # 20 ms poll interval
        self._sub.connect("inproc://python-to-lua")
        self._sub.setsockopt_string(zmq.SUBSCRIBE, "")

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

        Serializes payload to wire format "{topic} {json}" internally.
        """
        wire = f"{topic} {json.dumps(payload)}"
        await self._pub.send_string(wire)
        self.published_to_service.append({"topic": topic, "payload": payload})
        logger.debug(f"LuaSimulator → service: {topic}")

    async def _poll_loop(self) -> None:
        """Receive messages from the service and dispatch them."""
        while True:
            try:
                raw_bytes = await self._sub.recv()
                raw = raw_bytes.decode("utf-8")
                space = raw.find(" ")
                if space == -1:
                    logger.warning(f"LuaSimulator: malformed message: {raw[:80]}")
                    continue

                topic = raw[:space]
                try:
                    payload = json.loads(raw[space + 1:])
                except json.JSONDecodeError as exc:
                    logger.warning(f"LuaSimulator: JSON decode error on {topic}: {exc}")
                    continue

                self.received_from_service.append({"topic": topic, "payload": payload})
                logger.debug(f"LuaSimulator ← service: {topic}")

                if topic == "state.query" or topic.startswith("state.query."):
                    await self._respond_to_state_query(topic, payload)

                if topic == "dialogue.display":
                    self.done_event.set()

            except zmq.Again:
                # Poll timeout — yield to event loop, check for cancellation
                await asyncio.sleep(0)
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
    }

    async def _respond_to_state_query(self, topic: str, payload: dict[str, Any]) -> None:
        """Auto-respond to a state.query.* message using configured mocks."""
        request_id = payload.get("request_id")
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

        response = {
            "request_id": request_id,
            "data": mock.get("response", {}),
        }
        wire = f"state.response {json.dumps(response)}"
        await self._pub.send_string(wire)
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

        response = {
            "request_id": request_id,
            "data": {"results": results},
        }
        wire = f"state.response {json.dumps(response)}"
        await self._pub.send_string(wire)
        logger.debug(
            f"LuaSimulator: responded to batch query ({len(queries)} sub-queries, "
            f"request_id={request_id})"
        )

    def close(self) -> None:
        """Cancel poll task and close sockets. Does NOT terminate the shared context."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._sub.close()
        self._pub.close()
