"""Integration tests for multi-session (multi-tenant) behaviour.

Verifies that:
- Two sessions get independent ConfigMirror / SpeakerSelector instances
- Config sync to one session does not affect the other
- DialogueGenerator routes LLM calls through the session-aware factory
- State queries and publishes carry the session parameter
- Heartbeat ack is sent to the correct session
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.transport.session import DEFAULT_SESSION
from talker_service.transport.session_registry import SessionRegistry
from talker_service.handlers import config as config_handlers
from talker_service.handlers import events as event_handlers
from talker_service.dialogue.generator import DialogueGenerator
from talker_service.state.batch import BatchQuery, BatchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_batch_result(**kwargs):
    """Build a BatchResult from optional data dicts."""
    results = {}
    for key, data in kwargs.items():
        results[key] = {"ok": True, "data": data}
    return BatchResult(results)


class RecordingPublisher:
    """Publisher mock that records (topic, payload, session) tuples."""

    def __init__(self):
        self.calls: list[tuple[str, dict, str | None]] = []

    async def publish(self, topic, payload, *, session=None, r=None):
        self.calls.append((topic, payload, session))
        return True


class RecordingStateClient:
    """State client mock that records (batch_queries, session) tuples."""

    def __init__(self, result: BatchResult):
        self.result = result
        self.calls: list[tuple[list, str | None]] = []

    async def execute_batch(self, batch, *, timeout=None, session=None):
        queries = batch.build()
        self.calls.append((queries, session))
        return self.result


# ---------------------------------------------------------------------------
# Per-session config isolation
# ---------------------------------------------------------------------------

class TestPerSessionConfigIsolation:
    """Verify config mirrors are independent across sessions."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.registry = SessionRegistry()
        config_handlers.set_session_registry(self.registry)
        yield
        config_handlers._session_registry = None

    @pytest.mark.asyncio
    async def test_sync_creates_separate_mirrors(self):
        """config.sync to session A does not change session B."""
        await config_handlers.handle_config_sync(
            {"ai_model_method": 2, "custom_ai_model": "llama3"},
            "session_a",
        )
        await config_handlers.handle_config_sync(
            {"ai_model_method": 1, "custom_ai_model": "gpt-4o"},
            "session_b",
        )

        mirror_a = self.registry.get_config("session_a")
        mirror_b = self.registry.get_config("session_b")

        assert mirror_a.get("model_method") == 2
        assert mirror_a.get("model_name") == "llama3"
        assert mirror_b.get("model_method") == 1
        assert mirror_b.get("model_name") == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_one_session_leaves_other_unchanged(self):
        """config.update to session A does not touch session B."""
        # Sync both first
        await config_handlers.handle_config_sync(
            {"ai_model_method": 0, "custom_ai_model": "model_x"},
            "session_a",
        )
        await config_handlers.handle_config_sync(
            {"ai_model_method": 0, "custom_ai_model": "model_x"},
            "session_b",
        )

        # Update only session A
        await config_handlers.handle_config_update(
            {"custom_ai_model": "model_y"},
            "session_a",
        )

        assert self.registry.get_config("session_a").get("model_name") == "model_y"
        assert self.registry.get_config("session_b").get("model_name") == "model_x"


# ---------------------------------------------------------------------------
# DialogueGenerator session routing
# ---------------------------------------------------------------------------

class TestDialogueGeneratorSessionRouting:
    """Verify that DialogueGenerator threads session_id through publishes and state queries."""

    @pytest.fixture
    def state_client(self):
        return RecordingStateClient(_make_batch_result(
            mem={"narrative": None, "last_update_time_ms": 0},
            events=[],
            char={
                "game_id": "42", "name": "Hip", "faction": "stalker",
                "experience": "Experienced", "reputation": 0,
                "personality": "", "backstory": "", "weapon": "",
            },
            world={"loc": "", "weather": ""},
            alive={},
            personality={},
            backstory={},
        ))

    @pytest.fixture
    def publisher(self):
        return RecordingPublisher()

    @pytest.fixture
    def llm(self):
        client = AsyncMock()
        client.complete = AsyncMock(return_value="Stay safe out there.")
        return client

    @pytest.fixture
    def generator(self, llm, state_client, publisher):
        return DialogueGenerator(
            llm_client=llm,
            state_client=state_client,
            publisher=publisher,
            llm_timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_generate_from_event_passes_session_to_state_and_publish(
        self, generator, state_client, publisher
    ):
        """session_id flows through state queries and publish calls."""
        event = {
            "type": "DEATH",
            "witnesses": [{"game_id": "42", "name": "Hip", "faction": "stalker"}],
            "game_time_ms": 1000000,
            "world_context": "In Cordon",
        }

        await generator.generate_from_event(event, session_id="player_1")

        # State query should carry session
        assert len(state_client.calls) >= 1
        for _, sess in state_client.calls:
            assert sess == "player_1"

        # Publish should carry session
        assert len(publisher.calls) >= 1
        for topic, payload, sess in publisher.calls:
            assert sess == "player_1"

    @pytest.mark.asyncio
    async def test_generate_from_instruction_passes_session(
        self, generator, state_client, publisher
    ):
        """generate_from_instruction threads session_id."""
        event = {
            "type": "IDLE",
            "game_time_ms": 2000000,
            "world_context": "In Rostok",
        }

        await generator.generate_from_instruction("42", event, session_id="player_2")

        for _, sess in state_client.calls:
            assert sess == "player_2"
        for _, _, sess in publisher.calls:
            assert sess == "player_2"


# ---------------------------------------------------------------------------
# LLM factory session awareness
# ---------------------------------------------------------------------------

class TestSessionAwareLLMFactory:
    """Verify that get_llm(session_id) passes session to the factory."""

    def test_factory_receives_session_id(self):
        """A factory with a session_id param receives the session."""
        received = []

        def factory(session_id="__default__"):
            received.append(session_id)
            client = MagicMock()
            return client

        gen = DialogueGenerator(
            llm_client=factory,
            state_client=MagicMock(),
            publisher=MagicMock(),
        )

        gen.get_llm("session_x")
        assert received == ["session_x"]

    def test_factory_without_params_still_works(self):
        """A zero-arg factory is called without session_id (backward compat)."""
        called = []

        def factory():
            called.append(True)
            return MagicMock()

        gen = DialogueGenerator(
            llm_client=factory,
            state_client=MagicMock(),
            publisher=MagicMock(),
        )

        gen.get_llm("session_y")
        assert len(called) == 1


# ---------------------------------------------------------------------------
# Heartbeat session routing
# ---------------------------------------------------------------------------

class TestHeartbeatSessionRouting:
    """Verify heartbeat ack is published to the correct session."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.publisher = RecordingPublisher()
        event_handlers.set_publisher(self.publisher)
        event_handlers._last_heartbeat = None
        event_handlers._retry_queue = None
        # Set up a session registry so _get_mirror works
        self.registry = SessionRegistry()
        config_handlers.set_session_registry(self.registry)
        yield
        event_handlers._publisher = None
        config_handlers._session_registry = None

    @pytest.mark.asyncio
    async def test_heartbeat_ack_targets_session(self):
        """service.heartbeat.ack should be published to the requesting session."""
        # Sync config so is_synced is True (avoids extra config.request publish)
        await config_handlers.handle_config_sync({}, "player_3")

        await event_handlers.handle_heartbeat(
            {"alive": True, "game_time_ms": 100},
            "player_3",
        )

        # Find the ack publish
        acks = [(t, p, s) for t, p, s in self.publisher.calls if t == "service.heartbeat.ack"]
        assert len(acks) == 1
        assert acks[0][2] == "player_3"  # session

    @pytest.mark.asyncio
    async def test_config_request_targets_session_on_no_sync(self):
        """When config not synced, config.request goes to the heartbeat's session."""
        await event_handlers.handle_heartbeat(
            {"alive": True, "game_time_ms": 100},
            "player_4",
        )

        requests = [(t, p, s) for t, p, s in self.publisher.calls if t == "config.request"]
        assert len(requests) == 1
        assert requests[0][2] == "player_4"
