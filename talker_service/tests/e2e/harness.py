"""E2e test harness - wires WSRouter + LuaSimulator + ConversationManager.

Uses a MockWebSocket (in-memory asyncio queues, no TCP ports needed) and
SDK-level mocking for LLM calls.  All external payloads are captured for deep
assertion.

Startup order:
  1. Create WSRouter (auth disabled)
  2. Create MockWebSocket + LuaSimulator
  3. Start WSRouter.websocket_endpoint(mock_ws) as background task
  4. Start LuaSimulator background poll loop
  5. Wait a tick so both tasks are running
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import WebSocketDisconnect

from talker_service.transport.ws_router import WSRouter
from talker_service.state.client import StateQueryClient
from talker_service.dialogue.conversation import ConversationManager
from talker_service.llm.factory import get_llm_client
from talker_service.handlers import events as event_handlers

from .lua_simulator import LuaSimulator
from .mock_websocket import MockWebSocket


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
    """LLM request payloads captured from SDK mock calls."""
    ws_published: list[dict] = field(default_factory=list)
    """Non-state-query messages published by the service to Lua."""


def _mock_output_message(text: str):
    """Build a mock ResponseOutputMessage for the Responses API."""
    content_item = MagicMock()
    content_item.type = "output_text"
    content_item.text = text
    msg = MagicMock()
    msg.type = "message"
    msg.content = [content_item]
    return msg


def _mock_responses_api_result(response_id: str, text: str):
    """Build a mock Responses API Response object."""
    resp = MagicMock()
    resp.id = response_id
    resp.output = [_mock_output_message(text)]
    return resp


def _serialize_sdk_kwargs(kwargs: dict) -> dict:
    """Convert SDK kwargs into a JSON-serializable dict for payload capture.

    Message objects and other non-primitive types are converted to dicts.
    """
    result = {}
    for key, value in kwargs.items():
        if key in ("input", "messages") and isinstance(value, list):
            # Message dicts are already serializable (from to_dict())
            result[key] = value
        elif isinstance(value, (str, int, float, bool, type(None))):
            result[key] = value
        elif isinstance(value, list):
            result[key] = value
        elif isinstance(value, dict):
            result[key] = value
        else:
            result[key] = str(value)
    return result


class E2eHarness:
    """Wires and runs a single e2e scenario.

    Create via the pytest fixture in conftest.py.  Do not reuse across tests —
    each test gets a fresh harness with a fresh MockWebSocket.
    """

    def __init__(self) -> None:
        self._router: WSRouter | None = None
        self._mock_ws: MockWebSocket | None = None
        self._lua_sim: LuaSimulator | None = None
        self._ws_task: asyncio.Task | None = None
        self._started = False
        self.last_result: RunResult | None = None
        self._captured_calls: list[HttpCall] = []

    async def _setup(self, state_mocks: dict) -> None:
        """Internal setup called once per scenario."""
        # WSRouter with auth explicitly disabled (empty tokens dict)
        self._router = WSRouter(tokens={})

        # MockWebSocket bridges LuaSimulator ↔ WSRouter via asyncio queues
        self._mock_ws = MockWebSocket()
        self._lua_sim = LuaSimulator(self._mock_ws, state_mocks=state_mocks)

        # Wire up production handlers exactly as __main__.py does
        state_client = StateQueryClient(router=self._router, timeout=5.0)

        # Create LLM client — SDK methods will be mocked before running
        llm_client = get_llm_client(
            provider=0,
            api_key="test-key-sdk-mocked",
            force_new=True,
        )

        self._llm_client = llm_client

        conversation_manager = ConversationManager(
            llm_client=llm_client,
            state_client=state_client,
        )

        # Inject into event handler globals (same path as production)
        event_handlers.set_conversation_manager(conversation_manager)
        event_handlers.set_publisher(self._router)

        # Register handlers on router
        self._router.on("game.event", event_handlers.handle_game_event)

        # Start WSRouter endpoint task (reads from MockWebSocket)
        self._ws_task = asyncio.create_task(
            self._router.websocket_endpoint(self._mock_ws),
            name="ws-endpoint",
        )

        # Start LuaSimulator poll loop
        await self._lua_sim.start()

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

        # Build ordered mock responses from scenario llm_mocks
        mock_responses = [m["response"] for m in llm_mocks]
        self._captured_calls = []

        call_index = 0

        async def responses_create_side_effect(**kwargs):
            nonlocal call_index
            # Capture the request payload
            self._captured_calls.append(HttpCall(
                url="responses.create",
                body=_serialize_sdk_kwargs(kwargs),
            ))
            if call_index < len(mock_responses):
                content = mock_responses[call_index]
                call_index += 1
            else:
                content = "Fallback response."
            return _mock_responses_api_result(f"resp_e2e_{call_index}", content)

        async def completions_create_side_effect(**kwargs):
            nonlocal call_index
            # Capture the request payload
            self._captured_calls.append(HttpCall(
                url="chat.completions.create",
                body=_serialize_sdk_kwargs(kwargs),
            ))
            if call_index < len(mock_responses):
                content = mock_responses[call_index]
                call_index += 1
            else:
                content = "Fallback response."
            # Return mock ChatCompletion
            msg = MagicMock()
            msg.content = content
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        # Mock SDK methods on the client instance
        self._llm_client._client.responses.create = AsyncMock(
            side_effect=responses_create_side_effect
        )
        self._llm_client._client.chat.completions.create = AsyncMock(
            side_effect=completions_create_side_effect
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

        result = self._collect_result()
        self.last_result = result
        return result

    def _collect_result(self) -> RunResult:
        """Build RunResult from captured data."""
        # State queries: received_from_service entries where topic starts with state.query.
        # Strip request_id (non-deterministic UUID) before asserting.
        state_queries = []
        ws_published = []

        for entry in self._lua_sim.received_from_service:
            topic = entry["topic"]
            payload = dict(entry["payload"])  # copy

            if topic == "state.query" or topic.startswith("state.query."):
                payload.pop("request_id", None)
                state_queries.append({"topic": topic, "payload": payload})
            elif topic == "state.response":
                pass  # Internal plumbing — skip
            elif topic == "state.mutate" or topic.startswith("state.mutate."):
                pass  # Mutation acks — skip (infrastructure, not app-level)
            else:
                # Everything else (dialogue.display, memory.update, etc.)
                ws_published.append({"topic": topic, "payload": payload})

        return RunResult(
            state_queries=state_queries,
            http_calls=self._captured_calls,
            ws_published=ws_published,
        )

    async def shutdown(self) -> None:
        """Tear down all resources."""
        if not self._started:
            return

        # Reset event handler globals
        event_handlers.set_conversation_manager(None)
        event_handlers.set_publisher(None)

        # Signal MockWebSocket to disconnect (breaks WSRouter receive loop)
        if self._mock_ws:
            self._mock_ws.disconnect()

        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._router:
            await self._router.stop()

        if self._lua_sim:
            self._lua_sim.close()

        self._started = False
