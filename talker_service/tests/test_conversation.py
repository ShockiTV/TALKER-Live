"""Tests for ConversationManager (two-step deterministic dialogue)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.conversation import (
    ConversationManager,
    build_witness_text,
    build_event_system_msg,
    build_bg_system_msg,
    build_mem_system_msg,
    _resolve_event_display_name,
    _normalise_character_ids,
)
from talker_service.dialogue.dedup_tracker import DeduplicationTracker
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
        assert manager._messages == []
        assert isinstance(manager._tracker, DeduplicationTracker)
        assert manager._tracker.event_count == 0
        assert manager._tracker.bg_count == 0
        assert manager._tracker.mem_count == 0

    def test_init_creates_default_background_generator(self, mock_llm_client, mock_state_client):
        """Test that BackgroundGenerator is auto-created if not provided."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        assert manager.background_generator is not None

    def test_build_system_prompt(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test system prompt contains world context and guidelines."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        prompt = manager._build_system_prompt("Location: Garbage. Time: 14:35.")

        assert "Location: Garbage" in prompt
        assert "STALKER" in prompt
        assert "Dialogue Guidelines" in prompt
        # Should NOT contain tool instructions or per-character persona
        assert "get_memories" not in prompt
        assert "[SPEAKER:" not in prompt


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
        """Test _inject_speaker_memory injects MEM: system msgs for new speakers."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": [{"text": "Patrol summary", "timestamp": 500}]},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {
            "game_id": "char_001",
            "background": {"traits": ["brave"], "backstory": "Veteran", "connections": []},
        }

        narrative = await manager._inject_speaker_memory(speaker)

        assert "Patrol summary" in narrative
        assert "SUMMARIES" in narrative
        # Should have injected MEM: system message
        mem_msgs = [m for m in manager._messages if m.role == "system" and m.content.startswith("MEM:")]
        assert len(mem_msgs) == 1
        assert "MEM:char_001:500" in mem_msgs[0].content
        assert manager._tracker.is_mem_injected("char_001", 500)

    @pytest.mark.asyncio
    async def test_inject_speaker_memory_diff(self, mock_state_client, mock_background_generator):
        """Test _inject_speaker_memory returns only new items for returning speakers."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        # Simulate a returning speaker with previously tracked memory
        manager._tracker.mark_mem("char_001", 50)

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

        speaker = {"game_id": "char_001", "background": None}

        narrative = await manager._inject_speaker_memory(speaker)

        assert "New encounter" in narrative
        assert "Old patrol" not in narrative  # Already tracked, not in narrative
        assert manager._tracker.is_mem_injected("char_001", 200)


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
        `_messages` alongside EVT:/BG: system messages.  When a second event
        triggers the picker for 2+ candidates the messages list sent to
        `complete()` must contain those prior turns so the LLM has
        conversational context.
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
            world_result, mem_result,  # event 1
            world_result, mem_result,  # event 2
        ]

        # --- First event ---
        await manager.handle_event(
            event=event1, candidates=candidates,
            world="Dark Valley, evening", traits={},
        )

        # After first event:
        # [0] system, [1] EVT:1000, [2] BG:char_001, [3] BG:char_003,
        # [4] user (dialogue pointer), [5] assistant (For Duty!)
        assert len(manager._messages) == 6

        # --- Second event ---
        await manager.handle_event(
            event=event2, candidates=candidates,
            world="Dark Valley, evening", traits={},
        )

        # captured_messages[2] = picker call for second event
        # [0] system, [1] EVT:1000, [2] BG:char_001, [3] BG:char_003,
        # [4] user (prior dialogue), [5] assistant (For Duty!),
        # [6] EVT:2000 (new event), [7] picker pointer (ephemeral)
        picker_msgs = captured_messages[2]
        assert len(picker_msgs) == 8

        # Verify prior dialogue turn is present
        assert picker_msgs[4].role == "user"
        assert picker_msgs[5].role == "assistant"
        assert picker_msgs[5].content == "For Duty!"

        # Verify picker message is pointer-based
        assert picker_msgs[7].role == "user"
        assert "EVT:2000" in picker_msgs[7].content
        assert "char_001" in picker_msgs[7].content
        assert "char_003" in picker_msgs[7].content


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
        manager._messages = [Message(role="system", content="test")]

        # Mock full memory fetch
        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": [{"text": "Recent patrol", "timestamp": 100}]},
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
        manager._messages = [Message(role="system", content="test")]

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": []},
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

        # System + user + assistant = 3 messages
        assert len(manager._messages) == 3
        assert manager._messages[1].role == "user"
        assert manager._messages[2].role == "assistant"
        assert manager._messages[2].content == "For Duty!"

    @pytest.mark.asyncio
    async def test_returns_empty_on_llm_error(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Test that dialogue generation returns empty string on LLM error."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": []},
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "background": None}
        mock_llm_client.complete.side_effect = TimeoutError("timed out")

        result = await manager._run_dialogue_generation(speaker, {"type": "death"}, mock_llm_client)

        assert result == ""
        # User message should be cleaned up on error
        assert len(manager._messages) == 1


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

        # State calls: world enrichment, then memory fetch
        mock_state_client.execute_batch.side_effect = [
            # World enrichment batch
            BatchResult({
                "scene": {"ok": True, "data": {}},
                "alive": {"ok": True, "data": {}},
            }),
            # Full memory fetch for dialogue step
            BatchResult({
                "mem_events": {"ok": True, "data": []},
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
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
                "mem_events": {"ok": True, "data": []},
                "mem_summaries": {"ok": True, "data": []},
                "mem_digests": {"ok": True, "data": []},
                "mem_cores": {"ok": True, "data": []},
            }),
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
                "mem_events": {"ok": True, "data": []},
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
                "mem_events": {"ok": True, "data": []},
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

        # System prompt should contain enriched world
        system_msg = manager._messages[0]
        assert "Hostile" in system_msg.content
        assert sample_world in system_msg.content


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
    """Test that handle_event injects EVT: and BG: system messages
       and deduplicates them across sequential events."""

    @pytest.mark.asyncio
    async def test_evt_injected_once(self, mock_llm_client, mock_state_client, mock_background_generator):
        """EVT: system message is injected once per unique timestamp."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        # Pre-seed – simulate an EVT already injected
        manager._messages = [Message(role="system", content="test")]
        manager._tracker.mark_event(1000)
        manager._messages.append(Message(role="system", content="EVT:1000 — DEATH: X killed Y\nWitnesses: A(1)"))

        event = {"type": "death", "timestamp": 1000, "context": {"actor": {"name": "X"}, "victim": {"name": "Y"}}}
        candidates = [{"game_id": "1", "name": "A", "faction": "loner", "background": None}]

        # Simulate the injection logic directly
        event_ts = event.get("timestamp", 0)
        if not manager._tracker.is_event_injected(event_ts):
            manager._messages.append(Message(role="system", content=build_event_system_msg(event, candidates)))
            manager._tracker.mark_event(event_ts)

        # Should not have injected a second EVT:1000
        evt_msgs = [m for m in manager._messages if m.content.startswith("EVT:1000")]
        assert len(evt_msgs) == 1

    @pytest.mark.asyncio
    async def test_bg_injected_per_candidate(self, mock_llm_client, mock_state_client, mock_background_generator):
        """BG: system messages are injected per candidate, not duplicated."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        candidates = [
            {"game_id": "1", "name": "Alpha", "faction": "loner", "background": {"traits": ["brave"], "backstory": "Vet.", "connections": []}},
            {"game_id": "2", "name": "Bravo", "faction": "dolg", "background": {"traits": ["loyal"], "backstory": "Soldier.", "connections": []}},
        ]

        # Inject BG: for each candidate (mimicking handle_event logic)
        for cand in candidates:
            char_id = str(cand["game_id"])
            if not manager._tracker.is_bg_injected(char_id):
                bg_text = manager._format_background(cand.get("background"))
                name = cand["name"]
                faction = cand["faction"]
                content = build_bg_system_msg(char_id, name, faction, bg_text)
                manager._messages.append(Message(role="system", content=content))
                manager._tracker.mark_bg(char_id)

        bg_msgs = [m for m in manager._messages if m.content.startswith("BG:")]
        assert len(bg_msgs) == 2

        # Second pass should not duplicate
        for cand in candidates:
            char_id = str(cand["game_id"])
            if not manager._tracker.is_bg_injected(char_id):
                manager._messages.append(Message(role="system", content="SHOULD NOT APPEAR"))
                manager._tracker.mark_bg(char_id)

        bg_msgs = [m for m in manager._messages if m.content.startswith("BG:")]
        assert len(bg_msgs) == 2  # no duplicates

    @pytest.mark.asyncio
    async def test_mem_injected_and_deduped(self, mock_llm_client, mock_state_client, mock_background_generator):
        """MEM: system messages are injected once per (char_id, ts) pair."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        # Inject a MEM message
        content = build_mem_system_msg("char_001", 100, "SUMMARIES", "A brief patrol summary.")
        manager._messages.append(Message(role="system", content=content))
        manager._tracker.mark_mem("char_001", 100)

        # Attempt to inject same again
        if not manager._tracker.is_mem_injected("char_001", 100):
            manager._messages.append(Message(role="system", content="DUPLICATE"))

        mem_msgs = [m for m in manager._messages if m.content.startswith("MEM:")]
        assert len(mem_msgs) == 1


# ---------------------------------------------------------------------------
# Picker pointer format tests
# ---------------------------------------------------------------------------


class TestPickerPointerFormat:
    """Tests verifying the pointer-based picker message format."""

    @pytest.mark.asyncio
    async def test_picker_message_is_pointer_based(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Picker user message should reference EVT:{ts} and list candidate IDs."""
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
        event = {"type": "death", "timestamp": 42000, "context": {}}

        captured = []

        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "char_001"

        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client)

        picker_msg = captured[0][-1]
        assert picker_msg.role == "user"
        assert "EVT:42000" in picker_msg.content
        assert "char_001" in picker_msg.content
        assert "char_003" in picker_msg.content
        # Should NOT contain inline JSON or full event descriptions
        assert "{" not in picker_msg.content

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


class TestDialoguePointerFormat:
    """Tests verifying the pointer-based dialogue user message format."""

    @pytest.mark.asyncio
    async def test_dialogue_message_references_event(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Dialogue user message should reference EVT:{ts} and contain character ID."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )
        manager._messages = [Message(role="system", content="test")]

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": [{"text": "A patrol memory.", "timestamp": 500}]},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Fanatic Warrior", "faction": "dolg", "background": None}
        event = {"type": "death", "timestamp": 42000}
        mock_llm_client.complete.return_value = "For Duty!"

        await manager._run_dialogue_generation(speaker, event, mock_llm_client)

        # User message (second-to-last) should be pointer-based
        user_msg = manager._messages[-2]
        assert user_msg.role == "user"
        assert "EVT:42000" in user_msg.content
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
        manager._messages = [Message(role="system", content="test")]

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "char_001", "name": "Nobody", "faction": "loner", "background": None}
        mock_llm_client.complete.return_value = "..."

        await manager._run_dialogue_generation(speaker, {"type": "idle", "timestamp": 99}, mock_llm_client)

        user_msg = manager._messages[-2]
        assert "EVT:99" in user_msg.content
        assert "Personal memories:" not in user_msg.content
