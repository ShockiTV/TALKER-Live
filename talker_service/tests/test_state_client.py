"""Tests for state query client and models."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.state import (
    StateQueryClient,
    StateQueryTimeout,
    MemoryContext,
    Character,
    Event,
    WorldContext,
)


class TestCharacterModel:
    """Tests for Character dataclass."""
    
    def test_from_dict_full(self):
        """Test creating Character from full dict."""
        data = {
            "game_id": "123",
            "name": "Hip",
            "faction": "stalker",
            "experience": "Experienced",
            "reputation": "Good",
            "personality": "curious and friendly",
            "backstory": "A young stalker seeking knowledge",
            "weapon": "AK-74",
            "visual_faction": None,
        }
        
        char = Character.from_dict(data)
        
        assert char.game_id == "123"
        assert char.name == "Hip"
        assert char.faction == "stalker"
        assert char.experience == "Experienced"
        assert char.reputation == "Good"
        assert char.personality == "curious and friendly"
    
    def test_from_dict_minimal(self):
        """Test creating Character from minimal dict with defaults."""
        data = {"game_id": 456, "name": "Unknown"}
        
        char = Character.from_dict(data)
        
        assert char.game_id == "456"  # Converted to string
        assert char.name == "Unknown"
        assert char.faction == "stalker"  # Default
        assert char.experience == "Experienced"  # Default
    
    def test_from_dict_with_disguise(self):
        """Test creating Character with visual_faction (disguise)."""
        data = {
            "game_id": "789",
            "name": "Player",
            "faction": "stalker",
            "visual_faction": "Duty",
        }
        
        char = Character.from_dict(data)
        
        assert char.visual_faction == "Duty"


class TestEventModel:
    """Tests for Event dataclass."""
    
    def test_from_dict_typed_event(self):
        """Test creating typed Event from dict."""
        data = {
            "type": "DEATH",
            "context": {
                "victim": {"game_id": "123", "name": "Bandit"},
                "killer": {"game_id": "456", "name": "Hip"},
            },
            "game_time_ms": 1000000,
            "world_context": "In Cordon at morning",
            "witnesses": [
                {"game_id": "456", "name": "Hip", "faction": "stalker"},
            ],
            "flags": {"is_silent": False},
        }
        
        event = Event.from_dict(data)
        
        assert event.type == "DEATH"
        assert event.context["victim"]["name"] == "Bandit"
        assert event.game_time_ms == 1000000
        assert len(event.witnesses) == 1
        assert event.witnesses[0].name == "Hip"
    
    def test_from_dict_legacy_event(self):
        """Legacy content field is ignored - events must be typed."""
        data = {
            "content": "Hip killed a Bandit",
            "game_time_ms": 500000,
        }
        
        event = Event.from_dict(data)
        
        assert event.type is None
        # content field no longer exists - legacy events are ignored
    
    def test_from_dict_with_flags(self):
        """Test creating event with custom flags."""
        data = {
            "type": "CUSTOM",
            "context": {"message": "Something happened"},
            "game_time_ms": 2000000,
            "flags": {"is_important": True, "is_silent": False},
        }
        
        event = Event.from_dict(data)
        
        assert event.flags.get("is_important") is True
        assert event.flags.get("is_silent") is False


class TestMemoryContextModel:
    """Tests for MemoryContext dataclass."""
    
    def test_from_dict_with_narrative(self):
        """Test creating MemoryContext with narrative."""
        data = {
            "character_id": "123",
            "narrative": "Hip has been exploring the Zone...",
            "last_update_time_ms": 3000000,
            "new_events": [
                {"type": "DIALOGUE", "game_time_ms": 3500000},
                {"type": "DEATH", "game_time_ms": 4000000},
            ],
        }
        
        ctx = MemoryContext.from_dict(data)
        
        assert ctx.character_id == "123"
        assert "exploring the Zone" in ctx.narrative
        assert ctx.last_update_time_ms == 3000000
        assert len(ctx.new_events) == 2
        assert ctx.new_events[0].type == "DIALOGUE"
    
    def test_from_dict_empty_narrative(self):
        """Test creating MemoryContext with no narrative."""
        data = {
            "character_id": "456",
            "narrative": None,
            "new_events": [],
        }
        
        ctx = MemoryContext.from_dict(data)
        
        assert ctx.narrative is None
        assert len(ctx.new_events) == 0


class TestWorldContextModel:
    """Tests for WorldContext dataclass."""
    
    def test_from_dict_full(self):
        """Test creating WorldContext from full dict."""
        data = {
            "location": "Cordon",
            "location_technical": "l01_escape",
            "nearby_smart_terrain": "Rookie Village",
            "time_of_day": "morning",
            "weather": "clear",
            "emission": "",
            "game_time_ms": 5000000,
        }
        
        ctx = WorldContext.from_dict(data)
        
        assert ctx.location == "Cordon"
        assert ctx.nearby_smart_terrain == "Rookie Village"
        assert ctx.time_of_day == "morning"
        assert ctx.weather == "clear"
        assert ctx.emission == ""


class TestStateQueryClient:
    """Tests for StateQueryClient."""
    
    @pytest.fixture
    def mock_router(self):
        """Create a mock router for testing."""
        router = MagicMock()
        router.publish = AsyncMock(return_value=True)
        router.create_request = MagicMock()
        return router
    
    @pytest.mark.asyncio
    async def test_query_memories_success(self, mock_router):
        """Test successful memory query."""
        # Set up mock response
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "data": {
                "character_id": "123",
                "narrative": "Test narrative",
                "last_update_time_ms": 1000,
                "new_events": [],
            }
        })
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router, timeout=5.0)
        result = await client.query_memories("123")
        
        assert isinstance(result, MemoryContext)
        assert result.character_id == "123"
        assert result.narrative == "Test narrative"
        mock_router.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_events_recent(self, mock_router):
        """Test querying recent events."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "data": {
                "events": [
                    {"type": "DEATH", "game_time_ms": 1000},
                    {"type": "DIALOGUE", "game_time_ms": 2000},
                ],
                "count": 2,
            }
        })
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router)
        events = await client.query_events_recent(since_ms=0, limit=10)
        
        assert len(events) == 2
        assert events[0].type == "DEATH"
        assert events[1].type == "DIALOGUE"
    
    @pytest.mark.asyncio
    async def test_query_character(self, mock_router):
        """Test querying character by ID."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "data": {
                "character": {
                    "game_id": "456",
                    "name": "Hip",
                    "faction": "stalker",
                }
            }
        })
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router)
        char = await client.query_character("456")
        
        assert isinstance(char, Character)
        assert char.name == "Hip"
    
    @pytest.mark.asyncio
    async def test_query_characters_nearby(self, mock_router):
        """Test querying nearby characters."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "data": {
                "characters": [
                    {"game_id": "1", "name": "Hip", "faction": "stalker"},
                    {"game_id": "2", "name": "Wolf", "faction": "stalker"},
                ],
                "count": 2,
            }
        })
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router)
        chars = await client.query_characters_nearby(radius=50.0)
        
        assert len(chars) == 2
        assert chars[0].name == "Hip"
        assert chars[1].name == "Wolf"
    
    @pytest.mark.asyncio
    async def test_query_world_context(self, mock_router):
        """Test querying world context."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "data": {
                "location": "Rostok",
                "time_of_day": "evening",
                "weather": "cloudy",
            }
        })
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router)
        ctx = await client.query_world_context()
        
        assert isinstance(ctx, WorldContext)
        assert ctx.location == "Rostok"
        assert ctx.time_of_day == "evening"
    
    @pytest.mark.asyncio
    async def test_query_publish_failure(self, mock_router):
        """Test handling publish failure."""
        mock_router.publish = AsyncMock(return_value=False)
        mock_router.create_request.return_value = asyncio.get_event_loop().create_future()
        
        client = StateQueryClient(mock_router)
        
        with pytest.raises(ConnectionError, match="Failed to publish"):
            await client.query_memories("123")
    
    @pytest.mark.asyncio
    async def test_query_timeout(self, mock_router):
        """Test handling query timeout."""
        # Create a future that will timeout
        future = asyncio.get_event_loop().create_future()
        
        async def timeout_after():
            await asyncio.sleep(0.1)
            if not future.done():
                future.set_exception(TimeoutError("Request timed out"))
        
        asyncio.create_task(timeout_after())
        mock_router.create_request.return_value = future
        
        client = StateQueryClient(mock_router, timeout=0.05)
        
        with pytest.raises(TimeoutError):
            await client.query_memories("123")


class TestStateQueryTimeout:
    """Tests for StateQueryTimeout exception."""

    def test_is_subclass_of_timeout_error(self):
        """StateQueryTimeout must be a subclass of TimeoutError."""
        assert issubclass(StateQueryTimeout, TimeoutError)

    def test_caught_by_except_timeout_error(self):
        """Existing ``except TimeoutError`` handlers must still catch it."""
        with pytest.raises(TimeoutError):
            raise StateQueryTimeout("test")

    def test_caught_by_except_state_query_timeout(self):
        """Can be caught specifically as StateQueryTimeout."""
        with pytest.raises(StateQueryTimeout):
            raise StateQueryTimeout("test")

    def test_default_attributes(self):
        """Default topic and character_id are None."""
        exc = StateQueryTimeout()
        assert exc.topic is None
        assert exc.character_id is None
        assert str(exc) == "State query timed out"

    def test_custom_attributes(self):
        """Topic and character_id are stored when provided."""
        exc = StateQueryTimeout(
            "query timed out",
            topic="state.query.memories",
            character_id="123",
        )
        assert exc.topic == "state.query.memories"
        assert exc.character_id == "123"
        assert str(exc) == "query timed out"

    @pytest.mark.asyncio
    async def test_send_query_raises_state_query_timeout(self):
        """_send_query re-raises TimeoutError as StateQueryTimeout with metadata."""
        router = MagicMock()
        router.publish = AsyncMock(return_value=True)
        
        future = asyncio.get_event_loop().create_future()
        
        async def timeout_after():
            await asyncio.sleep(0.05)
            if not future.done():
                future.set_exception(TimeoutError("Request timed out"))
        
        asyncio.create_task(timeout_after())
        router.create_request.return_value = future
        
        client = StateQueryClient(router, timeout=5.0)
        
        with pytest.raises(StateQueryTimeout) as exc_info:
            await client.query_memories("456")
        
        assert exc_info.value.topic == "state.query.memories"
        assert exc_info.value.character_id == "456"

    @pytest.mark.asyncio
    async def test_send_query_timeout_for_world_context(self):
        """World context query (no character_id) sets character_id=None."""
        router = MagicMock()
        router.publish = AsyncMock(return_value=True)
        
        future = asyncio.get_event_loop().create_future()
        
        async def timeout_after():
            await asyncio.sleep(0.05)
            if not future.done():
                future.set_exception(TimeoutError("Request timed out"))
        
        asyncio.create_task(timeout_after())
        router.create_request.return_value = future
        
        client = StateQueryClient(router, timeout=5.0)
        
        with pytest.raises(StateQueryTimeout) as exc_info:
            await client.query_world_context()
        
        assert exc_info.value.topic == "state.query.world"
        assert exc_info.value.character_id is None
