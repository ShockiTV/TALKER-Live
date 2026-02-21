"""Tests for DialogueGenerator retry-queue integration."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.dialogue import DialogueGenerator
from talker_service.dialogue.retry_queue import DialogueRetryQueue
from talker_service.state.client import StateQueryTimeout


def _make_scene_ctx():
    """Create a mock SceneContext with required attributes."""
    ctx = MagicMock()
    ctx.loc = ""
    ctx.poi = ""
    ctx.time = ""
    ctx.weather = ""
    ctx.emission = ""
    ctx.psy_storm = ""
    ctx.sheltering = ""
    ctx.campfire = ""
    ctx.brain_scorcher_disabled = False
    ctx.miracle_machine_disabled = False
    return ctx


def _make_memory_ctx():
    """Create a mock MemoryContext."""
    ctx = MagicMock()
    ctx.narrative = None
    ctx.last_update_time_ms = 0
    ctx.new_events = []
    return ctx


def _make_character(game_id="123", name="Hip"):
    """Create a mock Character."""
    char = MagicMock()
    char.game_id = game_id
    char.name = name
    char.faction = "stalker"
    char.experience = "Experienced"
    char.reputation = "Good"
    char.personality = ""
    char.backstory = ""
    char.weapon = ""
    char.visual_faction = None
    return char


def _make_event(event_type="DEATH", witnesses=None, game_time_ms=1000000):
    """Build a minimal event dict."""
    if witnesses is None:
        witnesses = [{"game_id": "123", "name": "Hip", "faction": "stalker"}]
    return {
        "type": event_type,
        "witnesses": witnesses,
        "game_time_ms": game_time_ms,
        "world_context": "In Cordon",
    }


# ---------------------------------------------------------------------------
# With retry queue
# ---------------------------------------------------------------------------

class TestGeneratorWithRetryQueue:
    """Generator defers StateQueryTimeout to retry queue."""

    @pytest.fixture
    def setup(self):
        """Create generator with mocks + retry queue."""
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Some dialogue")

        state = AsyncMock()
        state.query_memories = AsyncMock(return_value=_make_memory_ctx())
        state.query_character = AsyncMock(return_value=_make_character())
        state.query_world_context = AsyncMock(return_value=_make_scene_ctx())
        state._send_query = AsyncMock(return_value={})

        publisher = AsyncMock()
        publisher.publish = AsyncMock(return_value=True)

        retry_queue = DialogueRetryQueue(max_retries=5)

        gen = DialogueGenerator(
            llm_client=llm,
            state_client=state,
            publisher=publisher,
            llm_timeout=10.0,
            retry_queue=retry_queue,
        )
        return gen, state, publisher, retry_queue

    @pytest.mark.asyncio
    async def test_event_timeout_enqueues(self, setup):
        """StateQueryTimeout during event dialogue enqueues to retry queue."""
        gen, state, publisher, retry_queue = setup
        state.query_memories.side_effect = StateQueryTimeout(
            "timeout", topic="state.query.memories", character_id="123"
        )

        event = _make_event()
        await gen.generate_from_event(event)

        # No dialogue published
        publisher.publish.assert_not_called()
        # Item enqueued
        assert retry_queue.size == 1

    @pytest.mark.asyncio
    async def test_instruction_timeout_enqueues(self, setup):
        """StateQueryTimeout during instruction enqueues with speaker_id."""
        gen, state, publisher, retry_queue = setup
        state.query_memories.side_effect = StateQueryTimeout(
            "timeout", topic="state.query.memories", character_id="456"
        )

        event = _make_event(event_type="IDLE")
        await gen.generate_from_instruction("456", event)

        publisher.publish.assert_not_called()
        assert retry_queue.size == 1

        # Inspect queued item
        item = retry_queue._queue[0]
        assert item.method == "instruction"
        assert item.speaker_id == "456"

    @pytest.mark.asyncio
    async def test_world_context_timeout_enqueues(self, setup):
        """StateQueryTimeout during world context query is caught and deferred."""
        gen, state, publisher, retry_queue = setup
        # Memories and character succeed, world context times out
        state.query_world_context.side_effect = StateQueryTimeout(
            "timeout", topic="state.query.world"
        )

        event = _make_event()
        await gen.generate_from_event(event)

        # Should have been enqueued
        publisher.publish.assert_not_called()
        assert retry_queue.size == 1

    @pytest.mark.asyncio
    async def test_non_timeout_exception_not_enqueued(self, setup):
        """Non-timeout exceptions are NOT enqueued — just logged."""
        gen, state, publisher, retry_queue = setup
        state.query_memories.side_effect = RuntimeError("data corruption")

        event = _make_event()
        await gen.generate_from_event(event)

        # Not enqueued — RuntimeError is not transient
        assert retry_queue.size == 0
        publisher.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Without retry queue (backward compatibility)
# ---------------------------------------------------------------------------

class TestGeneratorWithoutRetryQueue:
    """Generator without retry queue — timeout errors are logged and discarded."""

    @pytest.fixture
    def setup(self):
        """Create generator with mocks, NO retry queue."""
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Hello stalker")

        state = AsyncMock()
        state.query_memories = AsyncMock(return_value=_make_memory_ctx())
        state.query_character = AsyncMock(return_value=_make_character())
        state.query_world_context = AsyncMock(return_value=_make_scene_ctx())
        state._send_query = AsyncMock(return_value={})

        publisher = AsyncMock()
        publisher.publish = AsyncMock(return_value=True)

        gen = DialogueGenerator(
            llm_client=llm,
            state_client=state,
            publisher=publisher,
            llm_timeout=10.0,
            # retry_queue=None (default)
        )
        return gen, state, publisher

    @pytest.mark.asyncio
    async def test_event_timeout_logged_not_enqueued(self, setup):
        """Without retry queue, StateQueryTimeout is logged and discarded."""
        gen, state, publisher = setup
        state.query_memories.side_effect = StateQueryTimeout("timeout")

        event = _make_event()
        # Should NOT raise — error is caught and logged
        await gen.generate_from_event(event)
        publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_instruction_timeout_logged_not_enqueued(self, setup):
        """Without retry queue, instruction timeout is handled gracefully."""
        gen, state, publisher = setup
        state.query_memories.side_effect = StateQueryTimeout("timeout")

        event = _make_event(event_type="IDLE")
        await gen.generate_from_instruction("123", event)
        publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_still_works(self, setup):
        """Normal dialogue generation is unchanged."""
        gen, state, publisher = setup

        event = _make_event()
        await gen.generate_from_event(event)

        publisher.publish.assert_called()
        call_args = publisher.publish.call_args
        assert call_args[0][0] == "dialogue.display"


# ---------------------------------------------------------------------------
# LLM errors are permanent failures (not enqueued)
# ---------------------------------------------------------------------------

class TestLLMTimeoutNotEnqueued:
    """LLM / network errors should NOT be retried via the retry queue.

    Only ``StateQueryTimeout`` (Lua pause) is transient.  An LLM-side timeout
    or HTTP error is a permanent failure for that request.
    """

    @pytest.fixture
    def setup(self):
        """Generator with retry queue, state queries succeed, LLM fails."""
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=TimeoutError("LLM read timeout"))

        state = AsyncMock()
        state.query_memories = AsyncMock(return_value=_make_memory_ctx())
        state.query_character = AsyncMock(return_value=_make_character())
        state.query_world_context = AsyncMock(return_value=_make_scene_ctx())
        state._send_query = AsyncMock(return_value={})

        publisher = AsyncMock()
        publisher.publish = AsyncMock(return_value=True)

        retry_queue = DialogueRetryQueue(max_retries=5)

        gen = DialogueGenerator(
            llm_client=llm,
            state_client=state,
            publisher=publisher,
            llm_timeout=10.0,
            retry_queue=retry_queue,
        )
        return gen, state, publisher, retry_queue, llm

    @pytest.mark.asyncio
    async def test_llm_timeout_not_enqueued_event(self, setup):
        """LLM timeout during event dialogue is permanent — not enqueued."""
        gen, state, publisher, retry_queue, llm = setup

        event = _make_event(witnesses=[
            {"game_id": "123", "name": "Hip", "faction": "stalker"},
        ])
        await gen.generate_from_event(event)

        # LLM was called (state queries succeeded)
        assert llm.complete.call_count >= 1
        # Nothing published
        publisher.publish.assert_not_called()
        # NOT enqueued — LLM error is permanent
        assert retry_queue.size == 0

    @pytest.mark.asyncio
    async def test_llm_timeout_not_enqueued_instruction(self, setup):
        """LLM timeout during instruction dialogue is permanent — not enqueued."""
        gen, state, publisher, retry_queue, llm = setup

        event = _make_event(event_type="IDLE")
        await gen.generate_from_instruction("123", event)

        assert llm.complete.call_count >= 1
        publisher.publish.assert_not_called()
        assert retry_queue.size == 0


# ---------------------------------------------------------------------------
# Attempt count preserved through retry cycle
# ---------------------------------------------------------------------------

class TestAttemptCountPreserved:
    """Verify _retry_attempt flows through the generator on re-enqueue."""

    @pytest.fixture
    def setup(self):
        """Generator where state queries always timeout."""
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Some dialogue")

        state = AsyncMock()
        # Always timeout on memories
        state.query_memories = AsyncMock(
            side_effect=StateQueryTimeout("timeout", topic="state.query.memories")
        )
        state.query_character = AsyncMock(return_value=_make_character())
        state.query_world_context = AsyncMock(return_value=_make_scene_ctx())
        state._send_query = AsyncMock(return_value={})

        publisher = AsyncMock()
        publisher.publish = AsyncMock(return_value=True)

        retry_queue = DialogueRetryQueue(max_retries=3)

        gen = DialogueGenerator(
            llm_client=llm,
            state_client=state,
            publisher=publisher,
            llm_timeout=10.0,
            retry_queue=retry_queue,
        )
        return gen, state, publisher, retry_queue

    @pytest.mark.asyncio
    async def test_attempt_count_stamped_and_forwarded(self, setup):
        """When a retry item is re-submitted, the event dict carries _retry_attempt."""
        gen, state, publisher, retry_queue = setup

        # Simulate: first attempt enqueues at attempt=1
        event = _make_event()
        await gen.generate_from_event(event)

        assert retry_queue.size == 1
        item = retry_queue._queue[0]
        assert item.attempt_count == 1

        # Clear speaker cooldowns so retry can re-pick the speaker
        gen.speakers._last_spoke = {}

        # flush() increments to attempt=2, stamps _retry_attempt=2 into event dict,
        # generator catches timeout again and re-enqueues with attempt_count=2
        retry_queue.flush(gen)
        await asyncio.sleep(0.05)

        assert retry_queue.size == 1
        item2 = retry_queue._queue[0]
        assert item2.attempt_count == 2

        # Clear cooldowns again for third attempt
        gen.speakers._last_spoke = {}

        # flush() again — increments to attempt=3, re-submits, generator re-enqueues at 3
        retry_queue.flush(gen)
        await asyncio.sleep(0.05)

        assert retry_queue.size == 1
        item3 = retry_queue._queue[0]
        assert item3.attempt_count == 3

        # Final flush — attempt_count=3 >= max_retries=3 → discarded
        retry_queue.flush(gen)
        await asyncio.sleep(0.05)

        assert retry_queue.size == 0
