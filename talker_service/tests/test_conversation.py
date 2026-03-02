"""Tests for ConversationManager (tool-based dialogue generation)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.conversation import ConversationManager
from talker_service.state.batch import BatchResult
from talker_service.llm.models import Message


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns [SPEAKER: id] dialogue."""
    client = MagicMock()
    client.complete = AsyncMock(return_value="[SPEAKER: char_001]\nGet out of here, stalker!")
    return client


@pytest.fixture
def mock_state_client():
    """Mock state query client for batch queries."""
    client = MagicMock()
    # Default: return empty successful batch result
    default_result = BatchResult({"dummy": {"ok": True, "data": []}})
    client.execute_batch = AsyncMock(return_value=default_result)
    return client


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
        },
        {
            "game_id": "char_003",
            "name": "Duty Patrol",
            "faction": "dolg",
            "rank": 320,
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
    
    def test_init(self, mock_llm_client, mock_state_client):
        """Test ConversationManager initialization."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            max_tool_iterations=5,
            llm_timeout=60.0,
        )
        
        assert manager.llm_client == mock_llm_client
        assert manager.state_client == mock_state_client
        assert manager.max_tool_iterations == 5
        assert manager.llm_timeout == 60.0
        assert "get_memories" in manager._tool_handlers
        assert "get_background" in manager._tool_handlers
    
    @pytest.mark.asyncio
    async def test_handle_get_memories_success(self, mock_state_client):
        """Test _handle_get_memories retrieves memory tiers."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )
        
        # Mock batch result with events and summaries
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
        
        result = await manager._handle_get_memories(
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
        
        mem_events_query = next(q for q in queries if q["id"] == "mem_events")
        assert mem_events_query["resource"] == "memory.events"
        assert mem_events_query["params"]["character_id"] == "char_001"
    
    @pytest.mark.asyncio
    async def test_handle_get_memories_partial_failure(self, mock_state_client):
        """Test _handle_get_memories handles partial tier failures."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )
        
        # Mock batch result where one tier fails
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
        
        result = await manager._handle_get_memories(
            character_id="char_001",
            tiers=["events", "summaries"],
        )
        
        assert len(result["events"]) == 1
        assert result["summaries"] == []  # Failed tier returns empty list
    
    @pytest.mark.asyncio
    async def test_handle_get_background_success(self, mock_state_client):
        """Test _handle_get_background retrieves background data."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )
        
        mock_state_client.execute_batch.return_value = BatchResult({
            "background": {
                "ok": True,
                "data": {
                    "traits": {"personality_id": "duty_zealot"},
                    "backstory": "Former militiaman...",
                    "connections": [],
                },
            },
        })
        
        result = await manager._handle_get_background(character_id="char_001")
        
        assert "traits" in result
        assert result["traits"]["personality_id"] == "duty_zealot"
        assert "backstory" in result
        
        # Verify batch query
        mock_state_client.execute_batch.assert_called_once()
        batch_arg = mock_state_client.execute_batch.call_args[0][0]
        queries = batch_arg.build()
        
        query_ids = [q["id"] for q in queries]
        assert "background" in query_ids
        
        bg_query = next(q for q in queries if q["id"] == "background")
        assert bg_query["resource"] == "memory.background"
    
    @pytest.mark.asyncio
    async def test_handle_get_background_failure(self, mock_state_client):
        """Test _handle_get_background returns empty dict on failure."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )
        
        mock_state_client.execute_batch.return_value = BatchResult({
            "background": {
                "ok": False,
                "error": "Character not found",
            },
        })
        
        result = await manager._handle_get_background(character_id="char_001")
        
        assert result == {}
    
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    def test_build_system_prompt(
        self,
        mock_get_faction,
        mock_resolve_personality,
        mock_llm_client,
        mock_state_client,
    ):
        """Test system prompt builder includes all context."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_get_faction.return_value = "Duty: military stalkers who value order..."
        mock_resolve_personality.return_value = "Zealous ideologue who sees the world in black and white..."
        
        prompt = manager._build_system_prompt(
            faction="dolg",
            personality="Zealous ideologue...",
            world="Location: Garbage. Time: 14:35.",
        )
        
        # Verify prompt contains key sections
        assert "Duty: military stalkers" in prompt
        assert "Zealous ideologue" in prompt
        assert "Location: Garbage" in prompt
        assert "get_memories" in prompt  # Tool instructions
        assert "get_background" in prompt
        assert "[SPEAKER:" in prompt  # Response format (with game_id placeholder)
        
        mock_get_faction.assert_called_once_with("dolg")
    
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.resolve_backstory")
    def test_build_event_message(
        self,
        mock_resolve_backstory,
        mock_resolve_personality,
        mock_llm_client,
        mock_state_client,
        sample_event,
        sample_candidates,
        sample_traits,
    ):
        """Test event message builder formats event and candidates."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_resolve_personality.side_effect = lambda pid: f"Personality: {pid}"
        mock_resolve_backstory.side_effect = lambda bid: f"Backstory: {bid}"
        
        message = manager._build_event_message(
            event=sample_event,
            candidates=sample_candidates,
            traits=sample_traits,
        )
        
        # Verify event type name
        assert "DEATH" in message or "death" in message
        
        # Verify actor/victim details
        assert "Fanatic Warrior" in message
        assert "Freedom Fighter" in message
        
        # Verify candidates list
        assert "char_001" in message or "Fanatic Warrior" in message
        assert "char_003" in message or "Duty Patrol" in message
        
        # Verify personality/backstory text (truncated to 200 chars)
        assert "Personality: duty_zealot" in message
    
    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    async def test_handle_event_basic(
        self,
        mock_get_faction,
        mock_resolve_personality,
        mock_llm_client,
        mock_state_client,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event returns speaker and dialogue from LLM response."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_get_faction.return_value = "Duty faction description..."
        mock_resolve_personality.return_value = "Zealot personality..."
        
        # Mock LLM response with [SPEAKER: id] format
        mock_llm_client.complete.return_value = "[SPEAKER: char_001]\nAnother Freedom scum eliminated!"
        
        # Mock empty memories (no pre-fetch data)
        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": []},
            "mem_summaries": {"ok": True, "data": []},
        })
        
        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )
        
        assert speaker_id == "char_001"
        assert "Another Freedom scum eliminated!" in dialogue_text
        
        # Verify LLM was called with proper messages
        mock_llm_client.complete.assert_called_once()
        call_args = mock_llm_client.complete.call_args[0][0]
        assert isinstance(call_args, list)
        assert call_args[0].role == "system"
        assert call_args[1].role == "user"
    
    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    async def test_handle_event_with_prefetch(
        self,
        mock_get_faction,
        mock_resolve_personality,
        mock_llm_client,
        mock_state_client,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event pre-fetches speaker memories before LLM call."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_get_faction.return_value = "Duty faction..."
        mock_resolve_personality.return_value = "Zealot personality..."
        
        # Mock memories returned by pre-fetch
        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {
                "ok": True,
                "data": [
                    {"text": "Patrolled Garbage", "timestamp": 100},
                    {"text": "Encountered bandits", "timestamp": 200},
                ],
            },
            "mem_summaries": {
                "ok": True,
                "data": [
                    {"text": "Recent patrol summary", "timestamp": 300},
                ],
            },
        })
        
        mock_llm_client.complete.return_value = "[SPEAKER: char_001]\nFreedom eliminated!"
        
        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )
        
        # Verify pre-fetch batch query was executed
        mock_state_client.execute_batch.assert_called_once()
        batch_arg = mock_state_client.execute_batch.call_args[0][0]
        queries = batch_arg.build()
        
        query_ids = [q["id"] for q in queries]
        assert "mem_events" in query_ids
        assert "mem_summaries" in query_ids
        
        # Verify LLM messages include memory context
        call_args = mock_llm_client.complete.call_args[0][0]
        assert len(call_args) == 3  # system, memory context, event
        assert call_args[1].role == "system"
        # Memory context shows entry counts, not full text
        assert "EVENTS: 2 entries" in call_args[1].content
        assert "SUMMARIES: 1 entries" in call_args[1].content
    
    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    async def test_handle_event_invalid_speaker_id(
        self,
        mock_get_faction,
        mock_resolve_personality,
        mock_llm_client,
        mock_state_client,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event falls back to first candidate if LLM returns invalid speaker."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_get_faction.return_value = "Duty faction..."
        mock_resolve_personality.return_value = "Zealot personality..."
        
        # Mock LLM returning speaker NOT in candidates list
        mock_llm_client.complete.return_value = "[SPEAKER: char_999]\nInvalid speaker!"
        
        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": []},
            "mem_summaries": {"ok": True, "data": []},
        })
        
        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )
        
        # Should fall back to first candidate
        assert speaker_id == "char_001"
        assert "Invalid speaker!" in dialogue_text
    
    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    async def test_handle_event_no_speaker_tag(
        self,
        mock_get_faction,
        mock_resolve_personality,
        mock_llm_client,
        mock_state_client,
        sample_event,
        sample_candidates,
        sample_world,
        sample_traits,
    ):
        """Test handle_event handles LLM response without [SPEAKER: id] tag."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_get_faction.return_value = "Duty faction..."
        mock_resolve_personality.return_value = "Zealot personality..."
        
        # Mock LLM returning plain text without speaker tag
        mock_llm_client.complete.return_value = "This dialogue has no speaker tag!"
        
        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_events": {"ok": True, "data": []},
            "mem_summaries": {"ok": True, "data": []},
        })
        
        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )
        
        # Should fall back to first candidate
        assert speaker_id == "char_001"
        assert "This dialogue has no speaker tag!" in dialogue_text
