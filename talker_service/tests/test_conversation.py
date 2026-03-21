"""Tests for ConversationManager (two-step deterministic dialogue)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.conversation import (
    ConversationManager,
    STATIC_SYSTEM_PROMPT,
    build_witness_text,
    build_event_system_msg,
    build_bg_system_msg,
    build_mem_system_msg,
    _resolve_event_display_name,
    _normalise_character_ids,
)
from talker_service.state.batch import BatchResult
from talker_service.llm.models import Message


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns plain dialogue text."""
    client = MagicMock()
    client.complete = AsyncMock(return_value="Get out of here, stalker!")
    return client


@pytest.fixture
def mock_state_client():
    """Mock state query client for batch queries."""
    client = MagicMock()
    # Default: return empty successful batch result
    default_result = BatchResult({"dummy": {"ok": True, "data": []}})
    client.execute_batch = AsyncMock(return_value=default_result)
    client.mutate_batch = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_background_generator():
    """Mock BackgroundGenerator that passes candidates through."""
    gen = MagicMock()
    gen.ensure_backgrounds = AsyncMock(side_effect=lambda c: c)
    return gen


@pytest.fixture
def sample_event():
    """Sample DEATH event payload."""
    return {
        "type": 0,  # DEATH
        "context": {
            "actor": {
                "game_id": "char_001",
                "name": "Fanatic Warrior",
                "faction": "dolg",
                "rank": 450,
            },
            "victim": {
                "game_id": "char_002",
                "name": "Freedom Fighter",
                "faction": "freedom",
                "rank": 380,
            },
        },
        "timestamp": 1234567890,
    }


@pytest.fixture
def sample_candidates():
    """Sample candidates list (speaker + witnesses)."""
    return [
        {
            "game_id": "char_001",
            "name": "Fanatic Warrior",
            "faction": "dolg",
            "rank": 450,
            "background": {
                "traits": ["zealous", "disciplined"],
                "backstory": "Former militiaman turned Duty zealot.",
                "connections": ["General Voronin"],
            },
        },
        {
            "game_id": "char_003",
            "name": "Duty Patrol",
            "faction": "dolg",
            "rank": 320,
            "background": {
                "traits": ["loyal", "cautious"],
                "backstory": "Standard Duty patrol soldier.",
                "connections": [],
            },
        },
    ]


@pytest.fixture
def sample_traits():
    """Sample traits map (personality + backstory IDs)."""
    return {
        "char_001": {
            "personality_id": "duty_zealot",
            "backstory_id": "duty_recruit",
        },
        "char_003": {
            "personality_id": "duty_soldier",
            "backstory_id": "generic_patrol",
        },
    }


@pytest.fixture
def sample_world():
    """Sample world description string."""
    return "Location: Garbage. Time: 14:35 (afternoon). Weather: Clear. Season: Summer."


class TestConversationManager:
    """Tests for ConversationManager class."""

    def test_init(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test ConversationManager initialization with new attributes."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
            llm_timeout=60.0,
        )

        assert manager.llm_client == mock_llm_client
        assert manager.state_client == mock_state_client
        assert manager.background_generator == mock_background_generator
        assert manager.llm_timeout == 60.0
        # Four-layer base: system, context user, assistant "Ready."
        assert len(manager._messages) == 3
        assert manager._messages[0].role == "system"
        assert manager._messages[1].role == "user"
        assert manager._messages[2].role == "assistant"
        assert manager._messages[2].content == "Ready."
        assert manager._context_block is not None
        assert manager._context_block.item_count == 0

    def test_init_creates_default_background_generator(self, mock_llm_client, mock_state_client):
        """Test that BackgroundGenerator is auto-created if not provided."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        assert manager.background_generator is not None

    def test_build_system_prompt(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test system prompt contains static dialogue rules only."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        prompt = manager._build_system_prompt("Location: Garbage. Time: 14:35.")

        assert "STALKER" in prompt
        assert "Dialogue Guidelines" in prompt
        # Should NOT contain tool instructions or per-character persona
        assert "get_memories" not in prompt
        assert "[SPEAKER:" not in prompt

    def test_system_prompt_has_no_dynamic_content(self, mock_llm_client, mock_state_client, mock_background_generator):
        """System prompt must not contain weather, time, location, or inhabitants."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        prompt = manager._build_system_prompt("Location: Garbage. Time: 14:35. Weather: Clear.")

        # Must not contain dynamic world state keywords
        prompt_lower = prompt.lower()
        for keyword in ["weather", "time:", "location:", "inhabitants", "garbage", "14:35", "clear"]:
            assert keyword.lower() not in prompt_lower, f"System prompt should not contain '{keyword}'"

    def test_system_prompt_is_identical_across_calls(self, mock_llm_client, mock_state_client, mock_background_generator):
        """System prompt must be byte-identical regardless of world input."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        prompt1 = manager._build_system_prompt("Location: Garbage. Time: 14:35.")
        prompt2 = manager._build_system_prompt("Location: Yantar. Time: 23:00. Weather: Rain.")
        prompt3 = manager._build_system_prompt("")

        assert prompt1 == prompt2 == prompt3


class TestMemoryHelpers:
    """Tests for memory fetching and formatting helpers."""

    @pytest.mark.asyncio
    async def test_fetch_memories_success(self, mock_state_client, mock_background_generator):
        """Test _fetch_memories retrieves memory tiers via batch query."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {
                "ok": True,
                "data": [
                    {"text": "Event 1", "timestamp": 100},
                    {"text": "Event 2", "timestamp": 200},
                ],
            },
            "mem_summaries": {
                "ok": True,
                "data": [
                    {"text": "Summary 1", "timestamp": 300},
                ],
            },
        })

        result = await manager._fetch_memories(
            character_id="char_001",
            tiers=["events", "summaries"],
        )

        assert "events" in result
        assert "summaries" in result
        assert len(result["events"]) == 2
        assert len(result["summaries"]) == 1

        # Verify batch query was constructed correctly
        mock_state_client.execute_batch.assert_called_once()
        batch_arg = mock_state_client.execute_batch.call_args[0][0]
        queries = batch_arg.build()
        query_ids = [q["id"] for q in queries]
        assert "mem_events" in query_ids
        assert "mem_summaries" in query_ids

    @pytest.mark.asyncio
    async def test_fetch_memories_partial_failure(self, mock_state_client, mock_background_generator):
        """Test _fetch_memories handles partial tier failures."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {
                "ok": True,
                "data": [{"text": "Event 1", "timestamp": 100}],
            },
            "mem_summaries": {
                "ok": False,
                "error": "Character not found",
            },
        })

        result = await manager._fetch_memories(
            character_id="char_001",
            tiers=["events", "summaries"],
        )

        assert len(result["events"]) == 1
        assert result["summaries"] == []  # Failed tier returns empty list

    def test_format_memories(self):
        """Test _format_memories produces readable text and tracks timestamps."""
        memories = {
            "events": [
                {"text": "Patrolled Garbage", "timestamp": 100},
                {"text": "Encountered bandits", "timestamp": 200},
            ],
            "summaries": [
                {"text": "Recent patrol summary", "timestamp": 300},
            ],
        }

        text, latest_ts = ConversationManager._format_memories(memories)

        assert "Patrolled Garbage" in text
        assert "Encountered bandits" in text
        assert "Recent patrol summary" in text
        assert latest_ts == 300

    def test_format_memories_empty(self):
        """Test _format_memories with no data."""
        text, latest_ts = ConversationManager._format_memories({})
        assert text == "No memories available."
        assert latest_ts == 0

    def test_format_background(self):
        """Test _format_background produces readable text."""
        bg = {
            "traits": ["brave", "cautious"],
            "backstory": "A veteran Zone stalker.",
            "connections": ["Sidorovich"],
        }

        text = ConversationManager._format_background(bg)

        assert "brave" in text
        assert "cautious" in text
        assert "A veteran Zone stalker." in text
        assert "Sidorovich" in text

    def test_format_background_none(self):
        """Test _format_background with None returns default."""
        text = ConversationManager._format_background(None)
        assert "No background on record" in text


class TestMemoryDiffInjection:
    """Tests for memory diff tracking and injection."""

    @pytest.mark.asyncio
    async def test_fetch_full_memory(self, mock_state_client, mock_background_generator):
        """Test _fetch_full_memory retrieves all tiers."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": [{"text": "Event", "timestamp": 100}]},
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        text, ts = await manager._fetch_full_memory("char_001")
        assert "Event" in text
        assert ts == 100

    @pytest.mark.asyncio
    async def test_fetch_diff_memory_filters_old(self, mock_state_client, mock_background_generator):
        """Test _fetch_diff_memory only returns events newer than since_ts."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {
                "ok": True,
                "data": [
                    {"text": "Old event", "timestamp": 50},
                    {"text": "New event", "timestamp": 200},
                ],
            },
        })

        text, ts = await manager._fetch_diff_memory("char_001", since_ts=100)
        assert "New event" in text
        assert "Old event" not in text
        assert ts == 200

    @pytest.mark.asyncio
    async def test_fetch_diff_memory_nothing_new(self, mock_state_client, mock_background_generator):
        """Test _fetch_diff_memory when no events are newer."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {
                "ok": True,
                "data": [{"text": "Old event", "timestamp": 50}],
            },
        })

        text, ts = await manager._fetch_diff_memory("char_001", since_ts=100)
        assert "No new memories" in text
        assert ts == 100  # unchanged

    @pytest.mark.asyncio
    async def test_inject_speaker_memory_first_time(self, mock_state_client, mock_background_generator):
        """Test _inject_speaker_memory adds MEM items to ContextBlock for new speakers."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        # _messages already has 3-message base from __init__

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": [{"text": "Patrol summary", "timestamp": 500}]},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {
            "game_id": "char_001",
            "name": "Wolf",
            "background": {"traits": ["brave"], "backstory": "Veteran", "connections": []},
        }

        narrative = await manager._inject_speaker_memory(speaker)

        assert "Patrol summary" in narrative
        assert "SUMMARIES" in narrative
        # ContextBlock should have the memory tracked
        assert manager._context_block.has_memory("char_001", 500)

    @pytest.mark.asyncio
    async def test_inject_speaker_memory_diff(self, mock_state_client, mock_background_generator):
        """Test _inject_speaker_memory returns only new items for returning speakers."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        # _messages already has 3-message base from __init__

        # Simulate a returning speaker with previously tracked memory via ContextBlock
        manager._context_block.add_memory("char_001", "Wolf", 50, "SUMMARIES", "Old patrol")

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {
                "ok": True,
                "data": [
                    {"text": "Old patrol", "timestamp": 50},
                    {"text": "New encounter", "timestamp": 200},
                ],
            },
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Wolf", "background": None}

        narrative = await manager._inject_speaker_memory(speaker)

        assert "New encounter" in narrative
        # Old patrol was already tracked, but still appears in narrative (all memories are returned)
        assert manager._context_block.has_memory("char_001", 200)


class TestSpeakerPicker:
    """Tests for the ephemeral speaker picker step."""

    @pytest.mark.asyncio
    async def test_single_candidate_skips_picker(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that picker is skipped for single candidate."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        candidates = [{"game_id": "char_001", "name": "Fanatic"}]

        result = await manager._run_speaker_picker(candidates, {}, mock_llm_client)

        assert result["game_id"] == "char_001"
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_picker_selects_correct_candidate(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that picker correctly parses LLM response to select candidate."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        candidates = [
            {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "rank": 450, "background": None},
            {"game_id": "char_003", "name": "Patrol", "faction": "dolg", "rank": 320, "background": None},
        ]

        mock_llm_client.complete.return_value = "char_003"

        result = await manager._run_speaker_picker(candidates, {"type": "death"}, mock_llm_client)

        assert result["game_id"] == "char_003"

    @pytest.mark.asyncio
    async def test_picker_removes_ephemeral_messages(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that picker messages are removed after selection."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        candidates = [
            {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "rank": 450, "background": None},
            {"game_id": "char_003", "name": "Patrol", "faction": "dolg", "rank": 320, "background": None},
        ]

        mock_llm_client.complete.return_value = "char_001"

        await manager._run_speaker_picker(candidates, {"type": "death"}, mock_llm_client)

        # Only the original system message should remain
        assert len(manager._messages) == 1
        assert manager._messages[0].role == "system"

    @pytest.mark.asyncio
    async def test_picker_fallback_on_invalid_response(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that picker falls back to first candidate on invalid LLM response."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        candidates = [
            {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "rank": 450, "background": None},
            {"game_id": "char_003", "name": "Patrol", "faction": "dolg", "rank": 320, "background": None},
        ]

        mock_llm_client.complete.return_value = "I think char_999 should respond"

        result = await manager._run_speaker_picker(candidates, {"type": "death"}, mock_llm_client)

        assert result["game_id"] == "char_001"

    @pytest.mark.asyncio
    async def test_picker_fallback_on_llm_error(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that picker falls back on LLM exception."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        candidates = [
            {"game_id": "char_001", "name": "Fanatic", "background": None},
            {"game_id": "char_003", "name": "Patrol", "background": None},
        ]

        mock_llm_client.complete.side_effect = TimeoutError("timed out")

        result = await manager._run_speaker_picker(candidates, {"type": "death"}, mock_llm_client)

        assert result["game_id"] == "char_001"
        # Messages should be cleaned up even on error
        assert len(manager._messages) == 1

    @pytest.mark.asyncio
    async def test_picker_sees_prior_dialogue_turns(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Picker on a second event sees the prior user+assistant dialogue in history.

        After the first handle_event the persistent dialogue messages stay in
        `_messages`.  When a second event triggers the picker for 2+ candidates
        the messages list sent to `complete()` must contain those prior turns
        so the LLM has conversational context.
        """
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "rank": 450, "background": None},
            {"game_id": "char_003", "name": "Patrol", "faction": "dolg", "rank": 320, "background": None},
        ]

        event1 = {"type": "death", "timestamp": 1000, "context": {"actor": {"name": "Wolf"}, "victim": {"name": "Bandit"}}}
        event2 = {"type": "injury", "timestamp": 2000, "context": {"actor": {"name": "Merc"}, "victim": {"name": "Loner"}}}

        # Memory batch result for compacted tiers (reused)
        mem_result = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })
        world_result = BatchResult({
            "scene": {"ok": True, "data": {}},
            "alive": {"ok": True, "data": {}},
        })
        events_result = BatchResult({
            "events": {"ok": True, "data": []},
        })

        # Capture message snapshots at each complete() call
        captured_messages: list[list[Message]] = []
        responses = [
            "char_001",     # picker → first event
            "For Duty!",    # dialogue → first event
            "char_003",     # picker → second event
            "Stay alert!",  # dialogue → second event
        ]
        call_idx = 0

        async def _capture_complete(messages, **kwargs):
            nonlocal call_idx
            # Snapshot the messages at call time (list is mutable)
            captured_messages.append(list(messages))
            resp = responses[call_idx]
            call_idx += 1
            return resp

        mock_llm_client.complete = _capture_complete

        mock_state_client.execute_batch.side_effect = [
            world_result, mem_result, events_result,  # event 1
            world_result, mem_result, events_result,  # event 2
        ]

        # --- First event ---
        await manager.handle_event(
            event=event1, candidates=candidates,
            world="Dark Valley, evening", traits={},
        )

        # After first event: 3 base + 1 assistant (user message is ephemeral) = 4
        assert len(manager._messages) == 4

        # --- Second event ---
        await manager.handle_event(
            event=event2, candidates=candidates,
            world="Dark Valley, evening", traits={},
        )

        # captured_messages[2] = picker call for second event
        picker_msgs = captured_messages[2]

        # Verify prior dialogue turn is present somewhere in the messages
        prior_turns = [m for m in picker_msgs if m.role == "assistant" and m.content == "For Duty!"]
        assert len(prior_turns) == 1

        # Verify picker message is the last user message
        last_user = [m for m in picker_msgs if m.role == "user"][-1]
        assert "React to event [" in last_user.content
        assert "char_001" in last_user.content
        assert "char_003" in last_user.content


class TestDialogueGeneration:
    """Tests for the persistent dialogue generation step."""

    @pytest.mark.asyncio
    async def test_generates_dialogue(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test _run_dialogue_generation returns LLM dialogue text."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        # Use the 3-message base from __init__

        # Mock full memory fetch
        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {
            "game_id": "char_001",
            "name": "Fanatic Warrior",
            "faction": "dolg",
            "background": {"traits": ["zealous"], "backstory": "Duty soldier.", "connections": []},
        }

        mock_llm_client.complete.return_value = "Another Freedom dog eliminated!"

        result = await manager._run_dialogue_generation(speaker, {"type": "death"}, mock_llm_client)

        assert result == "Another Freedom dog eliminated!"

    @pytest.mark.asyncio
    async def test_keeps_messages_in_history(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that dialogue messages are kept in conversation history."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        # 3-message base from __init__

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {
            "game_id": "char_001",
            "name": "Fanatic",
            "faction": "dolg",
            "background": None,
        }

        mock_llm_client.complete.return_value = "For Duty!"

        await manager._run_dialogue_generation(speaker, {"type": "death"}, mock_llm_client)

        # 3 base + 1 assistant = 4 messages (user message is ephemeral)
        assert len(manager._messages) == 4
        assert manager._messages[3].role == "assistant"
        assert manager._messages[3].content == "For Duty!"

    @pytest.mark.asyncio
    async def test_returns_empty_on_llm_error(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that dialogue generation returns empty string on LLM error."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        # 3-message base from __init__

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "background": None}
        mock_llm_client.complete.side_effect = TimeoutError("timed out")

        result = await manager._run_dialogue_generation(speaker, {"type": "death"}, mock_llm_client)

        assert result == ""
        # User message should be cleaned up on error — back to 3 base messages
        assert len(manager._messages) == 3


class TestHandleEvent:
    """Tests for the full handle_event orchestration."""

    @pytest.mark.asyncio
    async def test_basic_flow(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event returns speaker_id and dialogue from 2-step flow."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        # LLM calls: picker returns char_001, dialogue returns text
        mock_llm_client.complete.side_effect = [
            "char_001",  # picker
            "Another Freedom scum eliminated!",  # dialogue
        ]

        # State calls: world enrichment, memory fetch, witness events fetch
        mock_state_client.execute_batch.side_effect = [
            # World enrichment batch
            BatchResult({
                "scene": {"ok": True, "data": {}},
                "alive": {"ok": True, "data": {}},
            }),
            # Full memory fetch for dialogue step
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
            # Witness events fetch
            BatchResult({
                "events": {"ok": True, "data": []},
            }),
        ]

        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        assert speaker_id == "char_001"
        assert "Another Freedom scum eliminated!" in dialogue_text
        mock_background_generator.ensure_backgrounds.assert_called_once()

    @pytest.mark.asyncio
    async def test_filters_player_candidates(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_world,
        sample_traits,
    ):
        """Test handle_event filters out player (game_id=0) from candidates."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates_with_player = [
            {"game_id": "0", "name": "Player"},  # Should be filtered
            {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "rank": 450, "background": None},
        ]

        # Single NPC after filtering → picker skipped, only dialogue call
        mock_llm_client.complete.return_value = "Duty stands strong!"

        mock_state_client.execute_batch.side_effect = [
            BatchResult({"scene": {"ok": True, "data": {}}, "alive": {"ok": True, "data": {}}}),
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
            BatchResult({"events": {"ok": True, "data": []}}),
        ]

        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=candidates_with_player,
            world=sample_world,
            traits=sample_traits,
        )

        assert speaker_id == "char_001"
        assert "Duty stands strong!" in dialogue_text

    @pytest.mark.asyncio
    async def test_all_player_candidates(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_world,
        sample_traits,
    ):
        """Test handle_event returns empty when all candidates are player."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        speaker_id, text = await manager.handle_event(
            event=sample_event,
            candidates=[{"game_id": "0", "name": "Player"}],
            world=sample_world,
            traits=sample_traits,
        )

        assert speaker_id == "0"
        assert text == ""

    @pytest.mark.asyncio
    async def test_no_candidates_raises(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_world,
        sample_traits,
    ):
        """Test handle_event raises ValueError on empty candidates."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        with pytest.raises(ValueError, match="No candidates"):
            await manager.handle_event(
                event=sample_event,
                candidates=[],
                world=sample_world,
                traits=sample_traits,
            )

    @pytest.mark.asyncio
    async def test_witness_injection_called(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event injects witness events for all candidates."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_llm_client.complete.side_effect = [
            "char_001",  # picker
            "For Duty!",  # dialogue
        ]

        mock_state_client.execute_batch.side_effect = [
            BatchResult({"scene": {"ok": True, "data": {}}, "alive": {"ok": True, "data": {}}}),
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
            BatchResult({"events": {"ok": True, "data": []}}),
        ]

        await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        # mutate_batch should be called for witness injection
        mock_state_client.mutate_batch.assert_called_once()
        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert len(mutations) == 2  # Both candidates
        assert all(m["op"] == "append" for m in mutations)
        assert all(m["resource"] == "memory.events" for m in mutations)

    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock)
    async def test_enriches_world_context(
        self,
        mock_build_world,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event enriches world with dynamic data."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_build_world.return_value = "Faction standings: Duty <> Freedom = Hostile"

        mock_llm_client.complete.side_effect = [
            "char_001",
            "Duty stands strong!",
        ]

        mock_state_client.execute_batch.side_effect = [
            # World enrichment
            BatchResult({
                "scene": {"ok": True, "data": {"loc": "l03_agroprom"}},
                "alive": {"ok": True, "data": {}},
            }),
            # Memory fetch
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
            # Witness events fetch
            BatchResult({"events": {"ok": True, "data": []}}),
        ]

        await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        # System prompt is static (no enriched world) — world context goes in _messages[1]
        system_msg = manager._messages[0]
        assert system_msg.role == "system"
        assert system_msg.content == STATIC_SYSTEM_PROMPT


class TestWitnessText:
    """Tests for build_witness_text and event display name helpers."""

    def test_death_event(self):
        event = {
            "type": "death",
            "context": {
                "actor": {"name": "Wolf"},
                "victim": {"name": "Bandit"},
            },
        }
        text = build_witness_text(event)
        assert "DEATH" in text
        assert "Wolf" in text
        assert "killed" in text
        assert "Bandit" in text

    def test_event_without_victim(self):
        event = {
            "type": "artifact",
            "context": {
                "actor": {"name": "Wolf"},
            },
        }
        text = build_witness_text(event)
        assert "ARTIFACT" in text
        assert "Wolf" in text

    def test_event_without_actor(self):
        event = {
            "type": "emission",
            "context": {},
        }
        text = build_witness_text(event)
        assert "EMISSION" in text

    def test_numeric_event_type(self):
        assert _resolve_event_display_name(0) == "DEATH"
        assert _resolve_event_display_name(4) == "ARTIFACT"

    def test_string_event_type(self):
        assert _resolve_event_display_name("death") == "DEATH"
        assert _resolve_event_display_name("artifact") == "ARTIFACT"

    def test_unknown_event_type(self):
        assert _resolve_event_display_name("custom_event") == "CUSTOM_EVENT"
        assert _resolve_event_display_name(999) == "EVENT_999"


class TestNormaliseCharacterIds:
    """Tests for _normalise_character_ids helper."""

    def test_list_input(self):
        assert _normalise_character_ids(["a", "b"]) == ["a", "b"]

    def test_string_input(self):
        assert _normalise_character_ids("a") == ["a"]

    def test_none_with_legacy(self):
        assert _normalise_character_ids(None, character_id="a") == ["a"]

    def test_none_without_legacy(self):
        assert _normalise_character_ids(None) == []


# ---------------------------------------------------------------------------
# Tagged system message builder tests
# ---------------------------------------------------------------------------


class TestBuildEventSystemMsg:
    """Tests for build_event_system_msg."""

    def test_format_with_actor_and_victim(self):
        event = {
            "type": "death",
            "timestamp": 42000,
            "context": {
                "actor": {"name": "Wolf", "game_id": "12467"},
                "victim": {"name": "Bandit_7", "game_id": "99001"},
            },
        }
        candidates = [
            {"name": "Wolf", "game_id": "12467"},
            {"name": "Fanatic", "game_id": "34521"},
        ]
        msg = build_event_system_msg(event, candidates)
        assert msg.startswith("EVT:42000 — DEATH:")
        assert "Wolf killed Bandit_7" in msg
        assert "Witnesses: Wolf(12467), Fanatic(34521)" in msg

    def test_format_without_victim(self):
        event = {
            "type": "artifact",
            "timestamp": 5000,
            "context": {"actor": {"name": "Loner"}},
        }
        msg = build_event_system_msg(event, [{"name": "Loner", "game_id": "1"}])
        assert msg.startswith("EVT:5000 — ARTIFACT:")
        assert "Loner" in msg

    def test_format_without_actor(self):
        event = {
            "type": "emission",
            "timestamp": 9000,
            "context": {},
        }
        msg = build_event_system_msg(event, [])
        assert msg.startswith("EVT:9000 — EMISSION")
        assert "Witnesses:" in msg


class TestBuildBgSystemMsg:
    """Tests for build_bg_system_msg."""

    def test_basic_format(self):
        msg = build_bg_system_msg("12467", "Wolf", "Freedom", "Traits: brave\nBackstory: A veteran.")
        assert msg == "BG:12467 — Wolf (Freedom)\nTraits: brave\nBackstory: A veteran."


class TestBuildMemSystemMsg:
    """Tests for build_mem_system_msg."""

    def test_basic_format(self):
        msg = build_mem_system_msg("12467", 42000, "SUMMARIES", "Wolf recalls a patrol.")
        assert msg == "MEM:12467:42000 — [SUMMARIES] Wolf recalls a patrol."


# ---------------------------------------------------------------------------
# System message injection in handle_event
# ---------------------------------------------------------------------------


class TestSystemMessageInjection:
    """Test that ContextBlock deduplicates BG and MEM entries
       across sequential events (replaces old _tracker-based tests)."""

    @pytest.mark.asyncio
    async def test_bg_deduped_in_context_block(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Background entries are added once per character in ContextBlock."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        # Add a background
        added = manager._context_block.add_background("char_001", "Wolf", "Loner", "Veteran stalker.")
        assert added is True
        assert manager._context_block.has_background("char_001")

        # Adding same char_id again should be deduped
        added2 = manager._context_block.add_background("char_001", "Wolf", "Loner", "Veteran stalker.")
        assert added2 is False
        assert manager._context_block.item_count == 1

    @pytest.mark.asyncio
    async def test_mem_deduped_in_context_block(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Memory entries are added once per (char_id, ts) pair in ContextBlock."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        added = manager._context_block.add_memory("char_001", "Wolf", 100, "SUMMARIES", "A brief patrol.")
        assert added is True

        # Same (char_id, ts) should be deduped
        added2 = manager._context_block.add_memory("char_001", "Wolf", 100, "SUMMARIES", "A brief patrol.")
        assert added2 is False

        # Different ts should be added
        added3 = manager._context_block.add_memory("char_001", "Wolf", 200, "DIGESTS", "New encounter.")
        assert added3 is True
        assert manager._context_block.item_count == 2

    @pytest.mark.asyncio
    async def test_context_block_render_contains_entries(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Rendered context block contains both BG and MEM entries."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        manager._context_block.add_background("char_001", "Wolf", "Loner", "Veteran stalker.")
        manager._context_block.add_memory("char_001", "Wolf", 100, "SUMMARIES", "Patrol summary.")

        rendered = manager._context_block.render_markdown()
        assert "Wolf" in rendered
        assert "Veteran stalker." in rendered
        assert "Patrol summary." in rendered


# ---------------------------------------------------------------------------
# Picker pointer format tests
# ---------------------------------------------------------------------------


class TestPickerPointerFormat:
    """Tests verifying the inline picker message format."""

    @pytest.mark.asyncio
    async def test_picker_message_is_inline(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Picker user message should contain inline event description and candidate IDs."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "rank": 450, "background": None},
            {"game_id": "char_003", "name": "Patrol", "faction": "dolg", "rank": 320, "background": None},
        ]
        event = {"type": "death", "timestamp": 42000, "context": {}}

        captured = []

        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "char_001"

        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client)

        picker_msg = captured[0][-1]
        assert picker_msg.role == "user"
        # [ts] pointer format — no inline event type keyword
        assert "React to event [" in picker_msg.content
        assert "char_001" in picker_msg.content
        assert "char_003" in picker_msg.content

    @pytest.mark.asyncio
    async def test_picker_removes_exactly_2_messages(self, mock_llm_client, mock_state_client, mock_background_generator):
        """After picker, exactly 2 messages (user + assistant) are removed."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [
            Message(role="system", content="sys"),
            Message(role="system", content="EVT:1000 — DEATH"),
            Message(role="user", content="prior turn"),
            Message(role="assistant", content="prior response"),
        ]
        pre_count = len(manager._messages)

        mock_llm_client.complete = AsyncMock(return_value="char_001")
        candidates = [
            {"game_id": "char_001", "name": "A"},
            {"game_id": "char_002", "name": "B"},
        ]

        await manager._run_speaker_picker(candidates, {"timestamp": 2000}, mock_llm_client)

        assert len(manager._messages) == pre_count  # no net change


# ---------------------------------------------------------------------------
# Dialogue pointer format tests
# ---------------------------------------------------------------------------


class TestDialogueMessageFormat:
    """Tests verifying the inline dialogue user message format."""

    @pytest.mark.asyncio
    async def test_dialogue_message_contains_event(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Dialogue user message should contain inline event description and character ID."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": [{"text": "A patrol memory.", "timestamp": 500}]},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Fanatic Warrior", "faction": "dolg", "background": None}
        event = {"type": "death", "timestamp": 42000}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "For Duty!"
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(speaker, event, mock_llm_client)

        # User message captured before it was removed (ephemeral)
        user_msg = captured[0][-1]
        assert user_msg.role == "user"
        assert "React to event [" in user_msg.content
        assert "char_001" in user_msg.content
        assert "Fanatic Warrior" in user_msg.content
        assert "Personal memories:" in user_msg.content

    @pytest.mark.asyncio
    async def test_dialogue_message_no_narrative(self, mock_llm_client, mock_state_client, mock_background_generator):
        """When speaker has no memories, dialogue message omits narrative section."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Nobody", "faction": "loner", "background": None}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "..."
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(speaker, {"type": "idle", "timestamp": 99}, mock_llm_client)

        # User message captured before it was removed (ephemeral)
        user_msg = captured[0][-1]
        assert user_msg.role == "user"
        assert "React to event [" in user_msg.content
        assert "Personal memories:" not in user_msg.content


# ---------------------------------------------------------------------------
# Task 4.5 — Four-layer message layout validation
# ---------------------------------------------------------------------------

class TestFourLayerMessageLayout:
    """Validate the 4-layer message structure (system, context user, assistant ack, dialogue turns)."""

    def test_base_messages_structure(self, mock_llm_client, mock_state_client, mock_background_generator):
        """_messages[0:3] matches 4-layer spec: system, user context, assistant ack."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        assert len(manager._messages) == 3
        assert manager._messages[0].role == "system"
        assert manager._messages[0].content == STATIC_SYSTEM_PROMPT
        assert manager._messages[1].role == "user"
        assert manager._messages[1].content == ""  # empty context block initially
        assert manager._messages[2].role == "assistant"
        assert manager._messages[2].content == "Ready."

    def test_system_prompt_is_static_constant(self, mock_llm_client, mock_state_client, mock_background_generator):
        """System prompt is the STATIC_SYSTEM_PROMPT constant, not dynamically generated."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        assert manager._messages[0].content is STATIC_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_context_block_populates_messages_1(self, mock_llm_client, mock_state_client, mock_background_generator):
        """After adding BGs to context block, _messages[1] renders them."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._context_block.add_background("npc_1", "Wolf", "Loner", "A grizzled veteran.")
        manager._messages[1] = Message(role="user", content=manager._context_block.render_markdown())

        assert "Wolf" in manager._messages[1].content
        assert "Loner" in manager._messages[1].content
        assert manager._messages[1].role == "user"

    @pytest.mark.asyncio
    async def test_dialogue_turns_appended_after_base(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Dialogue user/assistant pairs are appended at index 3+."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Wolf", "faction": "stalker", "background": None}
        await manager._run_dialogue_generation(speaker, {"type": "idle", "timestamp": 99}, mock_llm_client)

        # 3 base + 1 assistant = 4 (user message is ephemeral)
        assert len(manager._messages) == 4
        assert manager._messages[3].role == "assistant"


# ---------------------------------------------------------------------------
# Task 6.3 — Picker ephemeral messages are cleaned up
# ---------------------------------------------------------------------------

class TestPickerEphemeralCleanup:
    """Verify picker messages are not present after dialogue step completes."""

    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_picker_messages_removed_after_handle_event(
        self, mock_world_ctx, mock_llm_client, mock_state_client, mock_background_generator,
        sample_event, sample_candidates, sample_traits, sample_world,
    ):
        """After handle_event with 2 candidates, picker messages must not remain."""
        call_count = 0

        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "char_001"  # picker
            return "Another kill."  # dialogue

        mock_llm_client.complete = AsyncMock(side_effect=_complete)

        # 3 batch calls: world enrichment, memory, witness events
        mock_state_client.execute_batch = AsyncMock(side_effect=[
            BatchResult({  # world enrichment
                "scene": {"ok": True, "data": {"loc": "l01_escape", "weather": "clear", "time": {"h": 14, "m": 35}, "emission": False, "psy_storm": False, "sheltering": False, "campfire": None, "brain_scorcher_disabled": False, "miracle_machine_disabled": False}},
                "alive": {"ok": True, "data": {}},
            }),
            BatchResult({  # witness events
                "events": {"ok": True, "data": []},
            }),
            BatchResult({  # memory
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
        ])

        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        # No picker-related messages should remain — only base 3 + assistant (user message is ephemeral)
        assert len(manager._messages) == 4
        roles = [m.role for m in manager._messages]
        assert roles == ["system", "user", "assistant", "assistant"]
        # The picker instruction mentioned "Candidates:" — must not be in any remaining message
        for msg in manager._messages:
            assert "Candidates:" not in msg.content


# ---------------------------------------------------------------------------
# Task 4 — Batch fetch events for all candidates before picker
# ---------------------------------------------------------------------------


class TestBatchEventFetch:
    """Tests for Task 4: batch-fetch events for all candidates before picker."""

    @pytest.mark.asyncio
    async def test_batch_query_for_N_candidates(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Events batch query issued BEFORE picker with one sub-query per candidate."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_llm_client.complete.side_effect = [
            "char_001",  # picker
            "For Duty!",  # dialogue
        ]
        mock_state_client.execute_batch.side_effect = [
            BatchResult({"scene": {"ok": True, "data": {}}, "alive": {"ok": True, "data": {}}}),
            BatchResult({
                "events_char_001": {"ok": True, "data": []},
                "events_char_003": {"ok": True, "data": []},
            }),
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
        ]

        await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        # Second execute_batch call should be the events batch for ALL candidates
        assert mock_state_client.execute_batch.call_count == 3
        calls = mock_state_client.execute_batch.call_args_list
        events_call_batch = calls[1][0][0]  # second call, first positional arg
        assert sorted(events_call_batch.query_ids) == sorted(["events_char_001", "events_char_003"])

    @pytest.mark.asyncio
    async def test_candidate_with_no_events(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_world,
        sample_traits,
    ):
        """A candidate returning empty events list is handled gracefully."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_A", "name": "Alpha", "faction": "dolg", "rank": 300, "background": None},
        ]

        mock_llm_client.complete.return_value = "Roger that."
        mock_state_client.execute_batch.side_effect = [
            BatchResult({"scene": {"ok": True, "data": {}}, "alive": {"ok": True, "data": {}}}),
            BatchResult({"events_npc_A": {"ok": True, "data": []}}),
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
        ]

        speaker_id, dialogue = await manager.handle_event(
            event=sample_event, candidates=candidates,
            world=sample_world, traits=sample_traits,
        )

        assert speaker_id == "npc_A"
        assert dialogue == "Roger that."

    @pytest.mark.asyncio
    async def test_batch_query_timeout_proceeds_with_empty(
        self,
        mock_llm_client,
        mock_state_client,
        mock_background_generator,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """TimeoutError on events batch → handle_event continues with empty events."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_llm_client.complete.side_effect = [
            "char_001",  # picker
            "All clear.",  # dialogue
        ]
        mock_state_client.execute_batch.side_effect = [
            BatchResult({"scene": {"ok": True, "data": {}}, "alive": {"ok": True, "data": {}}}),
            TimeoutError("events fetch timed out"),  # events batch times out
            BatchResult({
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
        ]

        # Should NOT raise — timeout is handled gracefully
        speaker_id, dialogue = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        assert speaker_id == "char_001"
        assert dialogue == "All clear."


# ---------------------------------------------------------------------------
# Task 5 — Picker with event list + [ts] pointers
# ---------------------------------------------------------------------------


class TestPickerWithEventList:
    """Tests for picker step with unified event list + [ts] pointers."""

    @pytest.mark.asyncio
    async def test_picker_includes_event_list(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Scenario: Picker prompt includes Recent events section with [ts] format."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None},
            {"game_id": "npc_2", "name": "Wolf", "faction": "loner", "background": None},
        ]
        event = {"type": "death", "ts": 1709912345, "context": {"actor": {"name": "Duty"}, "victim": {"name": "Freedom"}}}
        event_list_text = "[1709912001] CALLOUT \u2014 Echo (witnesses: Echo)\n[1709912345] DEATH \u2014 Duty killed Freedom (witnesses: Echo, Wolf)"

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "npc_1"
        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client, event_list_text=event_list_text)

        picker_msg = captured[0][-1]
        assert "**Recent events in area:**" in picker_msg.content
        assert "[1709912345]" in picker_msg.content
        assert "React to event [1709912345]." in picker_msg.content
        assert "npc_1" in picker_msg.content
        assert "npc_2" in picker_msg.content

    @pytest.mark.asyncio
    async def test_picker_no_separate_inline_description(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Scenario: Picker message does not inline event description separately."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_1", "name": "Echo"},
            {"game_id": "npc_2", "name": "Wolf"},
        ]
        event = {"type": "death", "ts": 5000, "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}}
        event_list_text = "[5000] DEATH \u2014 A killed B (witnesses: Echo, Wolf)"

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "npc_1"
        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client, event_list_text=event_list_text)

        picker_msg = captured[0][-1]
        # Should NOT contain old-style "Event: DEATH\nActor: A\nVictim: B"
        assert "Event:" not in picker_msg.content
        assert "Actor:" not in picker_msg.content

    @pytest.mark.asyncio
    async def test_picker_empty_event_list(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Picker with no event list still works (just ts pointer + candidates)."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_1", "name": "Echo"},
            {"game_id": "npc_2", "name": "Wolf"},
        ]
        event = {"type": "idle", "ts": 3000, "context": {}}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "npc_1"
        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client, event_list_text="")

        picker_msg = captured[0][-1]
        assert "React to event [3000]." in picker_msg.content
        assert "**Recent events in area:**" not in picker_msg.content


# ---------------------------------------------------------------------------
# Task 6 — Dialogue with ephemeral user message + event list
# ---------------------------------------------------------------------------


class TestDialogueWithEventList:
    """Tests for dialogue step with ephemeral user message + event list."""

    @pytest.mark.asyncio
    async def test_dialogue_includes_speaker_filtered_events(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Dialogue prompt includes speaker-filtered event list."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}
        event = {"type": "death", "ts": 1709912345, "context": {}}
        speaker_event_text = "[1709912001] CALLOUT — Echo (witnesses: Echo)\n[1709912345] DEATH — Duty killed Freedom (witnesses: Echo, Wolf)"

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "For the Zone!"
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, event, mock_llm_client,
            speaker_event_list_text=speaker_event_text,
        )

        user_msg = captured[0][-1]
        assert "**Recent events witnessed by Echo:**" in user_msg.content
        assert "[1709912345]" in user_msg.content
        assert "React to event [1709912345] as **Echo** (ID: npc_1)." in user_msg.content

    @pytest.mark.asyncio
    async def test_dialogue_no_separate_event_description(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Dialogue should not inline event description separately from event list."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}
        event = {"type": "death", "ts": 5000, "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "Words."
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, event, mock_llm_client,
            speaker_event_list_text="[5000] DEATH — A killed B (witnesses: Echo)",
        )

        user_msg = captured[0][-1]
        assert "Event:" not in user_msg.content
        assert "Actor:" not in user_msg.content

    @pytest.mark.asyncio
    async def test_dialogue_user_message_is_ephemeral(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: After dialogue, user message is removed; only assistant response persists."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}
        mock_llm_client.complete = AsyncMock(return_value="Dialogue text.")

        pre_count = len(manager._messages)

        await manager._run_dialogue_generation(
            speaker, {"type": "idle", "ts": 100, "context": {}}, mock_llm_client,
            speaker_event_list_text="",
        )

        # Only assistant response should be added (net +1)
        assert len(manager._messages) == pre_count + 1
        assert manager._messages[-1].role == "assistant"
        assert manager._messages[-1].content == "Dialogue text."
        # No user message in the final state
        for msg in manager._messages[pre_count:]:
            assert msg.role != "user"

    @pytest.mark.asyncio
    async def test_dialogue_no_narrative(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Speaker has no personal narrative memories yet."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Nobody", "faction": "loner", "background": None}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "..."
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, {"type": "idle", "ts": 99, "context": {}}, mock_llm_client,
            speaker_event_list_text="",
        )

        user_msg = captured[0][-1]
        assert "Personal memories:" not in user_msg.content
        assert "React to event [99]" in user_msg.content

    @pytest.mark.asyncio
    async def test_events_not_in_context_block(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Events appear in user message (ephemeral), not in the persistent context block."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "OK"
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, {"type": "death", "ts": 5000, "context": {}}, mock_llm_client,
            speaker_event_list_text="[5000] DEATH — events here (witnesses: Echo)",
        )

        # Context block (_messages[1]) should NOT contain event lines
        context_block = manager._messages[1].content
        assert "[5000]" not in context_block
        assert "witnesses:" not in context_block
