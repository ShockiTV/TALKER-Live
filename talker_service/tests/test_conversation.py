"""Tests for ConversationManager (tool-based dialogue generation)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.conversation import (
    ConversationManager,
    GET_CHARACTER_INFO_TOOL,
    GET_MEMORIES_TOOL,
    BACKGROUND_TOOL,
    TOOLS,
)
from talker_service.state.batch import BatchResult
from talker_service.llm.models import LLMToolResponse, Message, ToolCall


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns [SPEAKER: id] dialogue."""
    client = MagicMock()
    client.complete = AsyncMock(return_value="[SPEAKER: char_001]\nGet out of here, stalker!")
    client.complete_with_tools = AsyncMock(
        return_value=LLMToolResponse(text="[SPEAKER: char_001]\nGet out of here, stalker!")
    )
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
        assert "background" in manager._tool_handlers
    
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
        """Test _handle_background(action='read') retrieves background data."""
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
        
        result = await manager._handle_background(character_id="char_001", action="read")
        
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
        """Test _handle_background(action='read') returns empty dict on failure."""
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
        
        result = await manager._handle_background(character_id="char_001", action="read")
        
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
        assert "background" in prompt
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
        
        # Mock LLM response with [SPEAKER: id] format via complete_with_tools
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text="[SPEAKER: char_001]\nAnother Freedom scum eliminated!"
        )
        
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
        mock_llm_client.complete_with_tools.assert_called_once()
        call_args = mock_llm_client.complete_with_tools.call_args[0][0]
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
        
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text="[SPEAKER: char_001]\nFreedom eliminated!"
        )
        
        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )
        
        # Verify batch queries were executed:
        # 1st call = world context enrichment (query.world + query.characters_alive)
        # 2nd call = memory pre-fetch (mem_events + mem_summaries)
        assert mock_state_client.execute_batch.call_count == 2
        
        # Check memory pre-fetch batch (second call)
        memory_batch_arg = mock_state_client.execute_batch.call_args_list[1][0][0]
        queries = memory_batch_arg.build()
        
        query_ids = [q["id"] for q in queries]
        assert "mem_events" in query_ids
        assert "mem_summaries" in query_ids
        
        # Verify LLM messages include memory context
        call_args = mock_llm_client.complete_with_tools.call_args[0][0]
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
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text="[SPEAKER: char_999]\nInvalid speaker!"
        )
        
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
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text="This dialogue has no speaker tag!"
        )
        
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
    
    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    async def test_handle_event_enriches_world_with_faction_data(
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
        """Test handle_event enriches world string with dynamic faction data from query.world."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        
        mock_get_faction.return_value = "Duty faction..."
        mock_resolve_personality.return_value = "Zealot personality..."
        
        # World enrichment batch returns scene data with faction standings + goodwill
        scene_result = BatchResult({
            "scene": {
                "ok": True,
                "data": {
                    "loc": "l03_agroprom",
                    "weather": "clear",
                    "faction_standings": {"dolg_freedom": -1500},
                    "player_goodwill": {"dolg": 1200},
                },
            },
            "alive": {
                "ok": True,
                "data": {},
            },
        })
        # Memory pre-fetch returns empty
        mem_result = BatchResult({
            "mem_events": {"ok": True, "data": []},
            "mem_summaries": {"ok": True, "data": []},
        })
        mock_state_client.execute_batch.side_effect = [scene_result, mem_result]
        
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text="[SPEAKER: char_001]\nDuty stands strong!"
        )
        
        await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )
        
        # Verify the system prompt contains enriched world context
        call_args = mock_llm_client.complete_with_tools.call_args[0][0]
        system_msg = call_args[0]
        assert system_msg.role == "system"
        # The enriched world should include faction standings
        assert "Faction standings:" in system_msg.content
        assert "Hostile" in system_msg.content  # dolg_freedom = -1500 → Hostile
        # The enriched world should include player goodwill
        assert "Player goodwill:" in system_msg.content
        assert "Great" in system_msg.content  # dolg = 1200 → Great
        # The original world string should still be present
        assert sample_world in system_msg.content


class TestGetCharacterInfoTool:
    """Tests for get_character_info tool schema, handler, and formatting."""

    def test_tool_schema_structure(self):
        """7.6: Verify GET_CHARACTER_INFO_TOOL schema has correct structure."""
        assert GET_CHARACTER_INFO_TOOL["type"] == "function"
        func = GET_CHARACTER_INFO_TOOL["function"]
        assert func["name"] == "get_character_info"
        params = func["parameters"]
        assert params["type"] == "object"
        assert "character_id" in params["properties"]
        assert params["properties"]["character_id"]["type"] == "string"
        assert params["required"] == ["character_id"]

    def test_tools_list_contains_all_three(self):
        """7.7: Verify TOOLS list contains all 3 tool definitions."""
        assert len(TOOLS) == 3
        tool_names = [t["function"]["name"] for t in TOOLS]
        assert "get_memories" in tool_names
        assert "background" in tool_names
        assert "get_character_info" in tool_names

    def test_handler_registered(self, mock_llm_client, mock_state_client):
        """Verify get_character_info handler is in _tool_handlers."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )
        assert "get_character_info" in manager._tool_handlers

    @pytest.mark.asyncio
    async def test_handle_get_character_info_success(self, mock_state_client):
        """7.1: Mock state_client, verify batch query structure and response."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )

        char_info_response = {
            "character": {
                "game_id": "12467",
                "name": "Wolf",
                "faction": "stalker",
                "gender": "male",
                "background": {"traits": ["brave"], "backstory": "A veteran", "connections": []},
            },
            "squad_members": [
                {
                    "game_id": "12468",
                    "name": "Sidorovich",
                    "faction": "stalker",
                    "gender": "male",
                    "background": None,
                },
            ],
        }

        mock_state_client.execute_batch.return_value = BatchResult({
            "char_info": {"ok": True, "data": char_info_response},
        })

        result = await manager._handle_get_character_info(character_id="12467")

        assert result["character"]["game_id"] == "12467"
        assert result["character"]["gender"] == "male"
        assert len(result["squad_members"]) == 1

        # Verify batch query structure
        mock_state_client.execute_batch.assert_called_once()
        batch_arg = mock_state_client.execute_batch.call_args[0][0]
        queries = batch_arg.build()
        assert len(queries) == 1
        assert queries[0]["id"] == "char_info"
        assert queries[0]["resource"] == "query.character_info"
        assert queries[0]["params"]["id"] == "12467"

    @pytest.mark.asyncio
    async def test_handle_get_character_info_empty_squad(self, mock_state_client):
        """7.2: Verify squad_members: [] passthrough."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "char_info": {
                "ok": True,
                "data": {
                    "character": {"game_id": "100", "name": "Loner", "faction": "stalker", "gender": "male", "background": None},
                    "squad_members": [],
                },
            },
        })

        result = await manager._handle_get_character_info(character_id="100")
        assert result["squad_members"] == []

    @pytest.mark.asyncio
    async def test_handle_get_character_info_failure(self, mock_state_client):
        """7.3: Verify error dict returned on query failure."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "char_info": {"ok": False, "error": "Character not found: 99999"},
        })

        result = await manager._handle_get_character_info(character_id="99999")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_get_character_info_exception(self, mock_state_client):
        """7.3b: Verify error dict when execute_batch raises."""
        manager = ConversationManager(
            llm_client=MagicMock(),
            state_client=mock_state_client,
        )

        mock_state_client.execute_batch.side_effect = TimeoutError("timed out")

        result = await manager._handle_get_character_info(character_id="12467")
        assert "error" in result

    @patch("talker_service.dialogue.conversation.resolve_faction_name")
    def test_format_tool_result_get_character_info(self, mock_resolve):
        """7.4: Verify readable formatting with gender and background."""
        mock_resolve.side_effect = lambda f: {"stalker": "Loners", "dolg": "Duty"}.get(f, f)

        result = {
            "character": {
                "game_id": "12467",
                "name": "Wolf",
                "faction": "stalker",
                "experience": "veteran",
                "gender": "male",
                "background": {
                    "traits": ["brave", "cautious"],
                    "backstory": "A veteran Zone stalker.",
                    "connections": ["Sidorovich"],
                },
            },
            "squad_members": [
                {
                    "game_id": "12468",
                    "name": "Fanatic",
                    "faction": "dolg",
                    "experience": "experienced",
                    "gender": "female",
                    "background": None,
                },
            ],
        }

        formatted = ConversationManager._format_tool_result("get_character_info", result)

        assert "Wolf" in formatted
        assert "Loners" in formatted
        assert "male" in formatted
        assert "brave" in formatted
        assert "A veteran Zone stalker." in formatted
        assert "Sidorovich" in formatted
        assert "Fanatic" in formatted
        assert "Duty" in formatted
        assert "female" in formatted
        assert "No background on record" in formatted

    def test_format_tool_result_get_character_info_error(self):
        """7.4b: Verify error result is JSON-serialized."""
        result = {"error": "Character not found"}
        formatted = ConversationManager._format_tool_result("get_character_info", result)
        parsed = json.loads(formatted)
        assert parsed["error"] == "Character not found"

    def test_format_tool_result_get_character_info_no_squad(self):
        """Verify 'No squad members' message when squad is empty."""
        result = {
            "character": {"game_id": "1", "name": "Solo", "faction": "stalker", "gender": "male", "background": None},
            "squad_members": [],
        }
        formatted = ConversationManager._format_tool_result("get_character_info", result)
        assert "No squad members" in formatted

    @pytest.mark.asyncio
    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    async def test_tool_loop_dispatches_get_character_info(
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
        """7.5: Mock complete_with_tools to call get_character_info, verify dispatch."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )

        mock_get_faction.return_value = "Duty faction..."
        mock_resolve_personality.return_value = "Zealot personality..."

        # First call: LLM requests get_character_info tool
        tool_call = ToolCall(
            id="call_1",
            name="get_character_info",
            arguments={"character_id": "char_001"},
        )
        tool_response = LLMToolResponse(tool_calls=[tool_call])

        # Second call: LLM produces final dialogue
        final_response = LLMToolResponse(
            text="[SPEAKER: char_001]\nI know my squad is nearby."
        )

        mock_llm_client.complete_with_tools.side_effect = [tool_response, final_response]

        # First call: world context enrichment (no scene data in result → skipped)
        # Second call: pre-fetch returns empty memories
        # Third call: character info query
        char_info_data = {
            "character": {"game_id": "char_001", "name": "Fanatic", "faction": "dolg", "gender": "male", "background": None},
            "squad_members": [],
        }
        mock_state_client.execute_batch.side_effect = [
            BatchResult({}),  # world context enrichment (no scene/alive keys → no enrichment)
            BatchResult({"mem_events": {"ok": True, "data": []}, "mem_summaries": {"ok": True, "data": []}}),
            BatchResult({"char_info": {"ok": True, "data": char_info_data}}),
        ]

        speaker_id, dialogue_text = await manager.handle_event(
            event=sample_event,
            candidates=sample_candidates,
            world=sample_world,
            traits=sample_traits,
        )

        assert speaker_id == "char_001"
        assert "squad" in dialogue_text.lower()

        # Verify LLM was called twice (tool call + final)
        assert mock_llm_client.complete_with_tools.call_count == 2

        # Verify state client was called for world enrichment, pre-fetch, AND character info
        assert mock_state_client.execute_batch.call_count == 3

    def test_system_prompt_includes_get_character_info(self, mock_llm_client, mock_state_client):
        """Verify system prompt describes get_character_info tool."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
        )

        prompt = manager._build_system_prompt(
            faction="stalker",
            personality="A cautious stalker...",
            world="Location: Cordon.",
        )

        assert "get_character_info" in prompt
        assert "squad" in prompt.lower()
