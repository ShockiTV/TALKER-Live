"""Tests for dialogue generation components."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.dialogue import DialogueGenerator, SpeakerSelector
from talker_service.dialogue.cleaner import clean_dialogue, extract_speaker_id
from talker_service.state.batch import BatchResult


class TestSpeakerSelector:
    """Tests for SpeakerSelector class."""
    
    def test_no_cooldown_initially(self):
        """Test speaker has no cooldown initially."""
        selector = SpeakerSelector(cooldown_ms=3000)
        
        assert selector.is_on_cooldown("123", 1000000) is False
    
    def test_cooldown_after_speaking(self):
        """Test speaker goes on cooldown after speaking."""
        selector = SpeakerSelector(cooldown_ms=3000)
        
        selector.set_spoke("123", 1000000)
        
        # Still on cooldown at 1001000 (1 second later)
        assert selector.is_on_cooldown("123", 1001000) is True
        
        # Off cooldown at 1004000 (4 seconds later)
        assert selector.is_on_cooldown("123", 1004000) is False
    
    def test_filter_by_cooldown(self):
        """Test filtering speakers by cooldown."""
        selector = SpeakerSelector(cooldown_ms=3000)
        
        speakers = [
            {"game_id": "1", "name": "Hip"},
            {"game_id": "2", "name": "Wolf"},
            {"game_id": "3", "name": "Fanatic"},
        ]
        
        # Put speaker 2 on cooldown
        selector.set_spoke("2", 1000000)
        
        # Filter at 1001000 (1 second later)
        available = selector.filter_by_cooldown(speakers, 1001000)
        
        assert len(available) == 2
        assert available[0]["name"] == "Hip"
        assert available[1]["name"] == "Fanatic"
    
    def test_clear_cooldown(self):
        """Test clearing a specific cooldown."""
        selector = SpeakerSelector(cooldown_ms=3000)
        
        selector.set_spoke("123", 1000000)
        assert selector.is_on_cooldown("123", 1001000) is True
        
        selector.clear_cooldown("123")
        assert selector.is_on_cooldown("123", 1001000) is False
    
    def test_clear_all_cooldowns(self):
        """Test clearing all cooldowns."""
        selector = SpeakerSelector(cooldown_ms=3000)
        
        selector.set_spoke("1", 1000000)
        selector.set_spoke("2", 1000000)
        
        selector.clear_all_cooldowns()
        
        assert selector.is_on_cooldown("1", 1001000) is False
        assert selector.is_on_cooldown("2", 1001000) is False


class TestDialogueCleaner:
    """Tests for dialogue cleaning functions."""
    
    def test_clean_removes_quotes(self):
        """Test removing outer quotes."""
        assert clean_dialogue('"Hello there!"') == "Hello there!"
        assert clean_dialogue("'What do you want?'") == "What do you want?"
    
    def test_clean_removes_name_prefix(self):
        """Test removing name prefixes."""
        assert clean_dialogue("Hip: Hello stalker!") == "Hello stalker!"
        assert clean_dialogue("[Wolf]: Get out of here!") == "Get out of here!"
    
    def test_clean_removes_asterisk_actions(self):
        """Test removing asterisk actions."""
        text = "*sighs* I don't know what to do. *looks around*"
        assert clean_dialogue(text) == "I don't know what to do."
    
    def test_clean_removes_bracketed_emotions(self):
        """Test removing bracketed emotions."""
        text = "[laughs] That's funny! (sighs) But also sad."
        assert clean_dialogue(text) == "That's funny! But also sad."
    
    def test_clean_handles_empty(self):
        """Test handling empty input."""
        assert clean_dialogue("") == ""
        assert clean_dialogue(None) == ""
    
    def test_clean_returns_empty_for_refusal(self):
        """Test returning empty for AI refusals."""
        assert clean_dialogue("I'm sorry, but I cannot assist with that.") == ""
        assert clean_dialogue("As an AI language model...") == ""


class TestExtractSpeakerId:
    """Tests for speaker ID extraction."""
    
    def test_extract_from_json(self):
        """Test extracting from JSON format."""
        assert extract_speaker_id('{"id": 123}') == "123"
        assert extract_speaker_id('{ "id": 456 }') == "456"
    
    def test_extract_from_labeled(self):
        """Test extracting from labeled format."""
        assert extract_speaker_id("ID: 789") == "789"
        assert extract_speaker_id("[ID: 101]") == "101"
        assert extract_speaker_id("The speaker ID is ID: 202") == "202"
    
    def test_extract_from_plain(self):
        """Test extracting plain number."""
        assert extract_speaker_id("303") == "303"
        assert extract_speaker_id("Speaker 404 should respond") == "404"
    
    def test_extract_returns_none_for_invalid(self):
        """Test returning None for invalid input."""
        assert extract_speaker_id("") is None
        assert extract_speaker_id(None) is None
        assert extract_speaker_id("no numbers here") is None


def _make_batch_result(
    mem=None, char=None, world=None, alive=None,
):
    """Build a BatchResult from optional data dicts."""
    results = {}
    if mem is not None:
        results["mem"] = {"ok": True, "data": mem}
    if char is not None:
        results["char"] = {"ok": True, "data": char}
    if world is not None:
        results["world"] = {"ok": True, "data": world}
    if alive is not None:
        results["alive"] = {"ok": True, "data": alive}
    return BatchResult(results)


class TestDialogueGenerator:
    """Tests for DialogueGenerator class."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        llm = AsyncMock()
        llm.complete = AsyncMock()
        return llm
    
    @pytest.fixture
    def mock_state(self):
        """Create mock state query client."""
        state = AsyncMock()
        # Default execute_batch returns sensible empty data
        state.execute_batch = AsyncMock(return_value=_make_batch_result(
            mem={"narrative": None, "last_update_time_ms": 0, "new_events": []},
            char={"game_id": "123", "name": "Hip", "faction": "stalker",
                  "experience": "Experienced", "reputation": 0,
                  "personality": "", "backstory": "", "weapon": ""},
            world={"loc": "", "weather": ""},
            alive={},
        ))
        return state
    
    @pytest.fixture
    def mock_publisher(self):
        """Create mock publisher."""
        pub = AsyncMock()
        pub.publish = AsyncMock(return_value=True)
        return pub
    
    @pytest.fixture
    def generator(self, mock_llm, mock_state, mock_publisher):
        """Create DialogueGenerator with mocks."""
        return DialogueGenerator(
            llm_client=mock_llm,
            state_client=mock_state,
            publisher=mock_publisher,
            llm_timeout=10.0,
        )
    
    @pytest.mark.asyncio
    async def test_generate_from_event_no_witnesses(self, generator):
        """Test that no dialogue is generated without witnesses."""
        event = {
            "type": "DEATH",
            "witnesses": [],
            "game_time_ms": 1000000,
        }
        
        await generator.generate_from_event(event)
        
        # No dialogue should be published
        generator.publisher.publish.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_generate_from_event_single_witness(
        self, generator, mock_llm, mock_state, mock_publisher
    ):
        """Test dialogue generation with single non-player witness."""
        # Set up mocks - complete() returns a string directly
        mock_llm.complete.return_value = "What the hell happened here?"
        
        # Set up batch result for the speaker's state queries
        mock_state.execute_batch = AsyncMock(return_value=_make_batch_result(
            mem={"narrative": None, "last_update_time_ms": 0, "new_events": []},
            char={"game_id": "123", "name": "Hip", "faction": "stalker",
                  "experience": "Experienced", "reputation": "Good",
                  "personality": "", "backstory": "", "weapon": ""},
            world={"loc": "", "weather": ""},
            alive={},
        ))
        
        event = {
            "type": "DEATH",
            "witnesses": [
                {"game_id": "123", "name": "Hip", "faction": "stalker"},
            ],
            "game_time_ms": 1000000,
            "world_context": "In Cordon at morning",
        }
        
        await generator.generate_from_event(event)
        
        # Dialogue should be published
        mock_publisher.publish.assert_called()
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == "dialogue.display"
        assert call_args[0][1]["speaker_id"] == "123"
    
    @pytest.mark.asyncio
    async def test_generate_from_event_filters_player(self, generator):
        """Test that player (game_id 0) is filtered from speakers."""
        # Only player as witness
        event = {
            "type": "DEATH",
            "witnesses": [
                {"game_id": "0", "name": "Player"},
            ],
            "game_time_ms": 1000000,
        }
        
        await generator.generate_from_event(event)
        
        # No dialogue should be published
        generator.publisher.publish.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_generate_from_event_respects_cooldown(
        self, generator, mock_llm, mock_state
    ):
        """Test that speaker cooldown is respected."""
        # Put speaker on cooldown
        generator.speakers.set_spoke("123", 1000000)
        
        event = {
            "type": "DEATH",
            "witnesses": [
                {"game_id": "123", "name": "Hip"},
            ],
            "game_time_ms": 1001000,  # Only 1 second later
        }
        
        await generator.generate_from_event(event)
        
        # No dialogue should be published (speaker on cooldown)
        generator.publisher.publish.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_generate_from_instruction(
        self, generator, mock_llm, mock_state, mock_publisher
    ):
        """Test direct dialogue generation bypassing speaker selection."""
        # Set up mocks - complete() returns a string directly
        mock_llm.complete.return_value = "Just passing through."
        
        # Set up batch result for the speaker's state queries
        mock_state.execute_batch = AsyncMock(return_value=_make_batch_result(
            mem={"narrative": None, "last_update_time_ms": 0, "new_events": []},
            char={"game_id": "456", "name": "Wolf", "faction": "stalker",
                  "experience": "Veteran", "reputation": "Good",
                  "personality": "", "backstory": "", "weapon": ""},
            world={"loc": "", "weather": ""},
            alive={},
        ))
        
        event = {
            "type": "IDLE",
            "game_time_ms": 2000000,
            "world_context": "In Rostok at evening",
        }
        
        await generator.generate_from_instruction("456", event)
        
        # Dialogue should be published for specified speaker
        mock_publisher.publish.assert_called()
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == "dialogue.display"
        assert call_args[0][1]["speaker_id"] == "456"
