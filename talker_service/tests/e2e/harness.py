"""E2e test harness — wires ZMQRouter + LuaSimulator + DialogueGenerator.

Uses inproc:// ZMQ transport (no OS socket permissions needed) and respx for
HTTP interception.  All external payloads are captured for deep assertion.

Startup order (critical for inproc://):
  1. Create shared zmq.asyncio.Context
  2. Create LuaSimulator (binds inproc://lua-to-python FIRST)
  3. Create ZMQRouter with shared context
  4. Start lua_sim.start() background task
  5. Start router.run() background task (connects to inproc://lua-to-python,
     binds inproc://python-to-lua)
  6. Wait a tick so both tasks are running
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import respx
import zmq.asyncio

from talker_service.transport.router import ZMQRouter
from talker_service.state.client import StateQueryClient
from talker_service.dialogue.generator import DialogueGenerator
from talker_service.llm.openai_client import OpenAIClient
from talker_service.handlers import events as event_handlers

from .lua_simulator import LuaSimulator


# Default timeout for waiting on dialogue.display to arrive
DEFAULT_TIMEOUT_S = 10.0


@dataclass
class HttpCall:
    url: str
    body: dict


@dataclass
class RunResult:
    """Captured wire-level payloads from a single e2e run."""
    state_queries: list[dict] = field(default_factory=list)
    """state.query.* messages sent by the service, request_id stripped."""
    http_calls: list[HttpCall] = field(default_factory=list)
    """HTTP requests captured by respx."""
    zmq_published: list[dict] = field(default_factory=list)
    """Non-state-query messages published by the service to Lua."""


class E2eHarness:
    """Wires and runs a single e2e scenario.

    Create via the pytest fixture in conftest.py.  Do not reuse across tests —
    each test gets a fresh harness with a fresh ZMQ context.
    """

    def __init__(self) -> None:
        self._ctx: zmq.asyncio.Context | None = None
        self._router: ZMQRouter | None = None
        self._lua_sim: LuaSimulator | None = None
        self._generator: DialogueGenerator | None = None
        self._router_task: asyncio.Task | None = None
        self._started = False
        self.last_result: RunResult | None = None

    async def _setup(self, state_mocks: dict) -> None:
        """Internal setup called once per scenario."""
        self._ctx = zmq.asyncio.Context()

        # LuaSimulator must bind first (inproc:// requires bind before connect
        # in older libzmq; with libzmq 4.x it's also fine the other way, but
        # explicit ordering is safer)
        self._lua_sim = LuaSimulator(self._ctx, state_mocks=state_mocks)

        # ZMQRouter uses the shared context, connects to lua-to-python, binds python-to-lua
        self._router = ZMQRouter(
            sub_endpoint="inproc://lua-to-python",
            pub_endpoint="inproc://python-to-lua",
            context=self._ctx,
        )

        # Wire up production handlers exactly as __main__.py does
        state_client = StateQueryClient(router=self._router, timeout=5.0)

        # Real OpenAI client — respx intercepts at httpx transport layer
        llm_client = OpenAIClient(api_key="test-key-respx-will-intercept")

        self._generator = DialogueGenerator(
            llm_client=llm_client,
            state_client=state_client,
            publisher=self._router,
            llm_timeout=5.0,
        )

        # Inject into event handler globals (same path as production)
        event_handlers.set_dialogue_generator(self._generator)
        event_handlers.set_publisher(self._router)

        # Register handlers on router
        self._router.on("game.event", event_handlers.handle_game_event)

        # Start background tasks
        await self._lua_sim.start()
        self._router_task = asyncio.create_task(self._router.run(), name="zmq-router")

        # Yield to event loop so both tasks start running
        await asyncio.sleep(0.05)
        self._started = True

    async def run(self, scenario: dict, timeout: float = DEFAULT_TIMEOUT_S) -> RunResult:
        """Run one scenario end-to-end and return captured payloads.

        Args:
            scenario: Loaded scenario dict (from load_scenario).
            timeout: Seconds to wait for dialogue.display before raising TimeoutError.
        """
        state_mocks = scenario.get("state_mocks", {})
        llm_mocks = scenario.get("llm_mocks", [])
        input_cfg = scenario["input"]

        await self._setup(state_mocks)

        # Build respx route list from llm_mocks (ordered — first call gets first mock)
        mock_responses = [m["response"] for m in llm_mocks]

        with respx.mock(assert_all_called=False) as mock_router:
            call_index = 0

            def side_effect(request: httpx.Request) -> httpx.Response:
                nonlocal call_index
                if call_index < len(mock_responses):
                    content = mock_responses[call_index]
                    call_index += 1
                else:
                    content = "Fallback response."

                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": content}}
                        ]
                    },
                )

            mock_router.post("https://api.openai.com/v1/chat/completions").mock(
                side_effect=side_effect
            )

            # Publish the input event
            await self._lua_sim.publish(
                topic=input_cfg["topic"],
                payload=input_cfg["payload"],
            )

            # Wait for done_event (dialogue.display received by LuaSimulator)
            try:
                await asyncio.wait_for(
                    self._lua_sim.done_event.wait(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError(
                    f"dialogue.display not received within {timeout}s"
                )

            # Allow any in-flight background tasks (e.g. memory compression) to settle
            await asyncio.sleep(0.05)

            result = self._collect_result(mock_router)
            self.last_result = result
            return result

    def _collect_result(self, mock_router: respx.MockRouter) -> RunResult:
        """Build RunResult from captured data."""
        # State queries: received_from_service entries where topic starts with state.query.
        # Strip request_id (non-deterministic UUID) before asserting.
        state_queries = []
        zmq_published = []

        for entry in self._lua_sim.received_from_service:
            topic = entry["topic"]
            payload = dict(entry["payload"])  # copy

            if topic == "state.query" or topic.startswith("state.query."):
                payload.pop("request_id", None)
                state_queries.append({"topic": topic, "payload": payload})
            elif topic != "state.response":
                # Everything else (dialogue.display, memory.update, etc.)
                zmq_published.append({"topic": topic, "payload": payload})

        # HTTP calls: parse exact request body from respx
        http_calls = []
        for call in mock_router.calls:
            body = json.loads(call.request.content)
            http_calls.append(HttpCall(url=str(call.request.url), body=body))

        return RunResult(
            state_queries=state_queries,
            http_calls=http_calls,
            zmq_published=zmq_published,
        )

    async def shutdown(self) -> None:
        """Tear down all resources."""
        if not self._started:
            return

        # Reset event handler globals
        event_handlers.set_dialogue_generator(None)
        event_handlers.set_publisher(None)

        if self._router_task and not self._router_task.done():
            self._router_task.cancel()
            try:
                await self._router_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._router:
            await self._router.shutdown()

        if self._lua_sim:
            self._lua_sim.close()

        if self._ctx:
            self._ctx.term()

        self._started = False
