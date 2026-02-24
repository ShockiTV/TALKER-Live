"""Tests for state query client and models (WSRouter transport)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from talker_service.state import (
    StateQueryClient,
    StateQueryTimeout,
)
from talker_service.state.models import (
    MemoryContext,
    Character,
    Event,
    SceneContext,
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
            "weapon": "AK-74",
            "visual_faction": None,
        }
        
        char = Character.from_dict(data)
        
        assert char.game_id == "123"
        assert char.name == "Hip"
        assert char.faction == "stalker"
        assert char.experience == "Experienced"
        assert char.reputation == "Good"
    
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
    """Tests for StateQueryClient with WSRouter."""
    
    @pytest.fixture
    def mock_router(self):
        """Create a mock WSRouter for testing."""
        router = MagicMock()
        router.publish = AsyncMock(return_value=True)
        router.create_request = MagicMock()
        return router
    
    @pytest.mark.asyncio
    async def test_send_query_success(self, mock_router):
        """Test successful _send_query returns data."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "data": {
                "character_id": "123",
                "narrative": "Test narrative",
            }
        })
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router, timeout=5.0)
        result = await client._send_query(
            "state.query.memories",
            {"character_id": "123"}
        )
        
        assert result["character_id"] == "123"
        assert result["narrative"] == "Test narrative"
        mock_router.publish.assert_called_once()
        # Verify r field is passed to publish
        _, kwargs = mock_router.publish.call_args
        assert "r" in kwargs
    
    @pytest.mark.asyncio
    async def test_publish_uses_r_field(self, mock_router):
        """Verify publish is called with r=request_id for WSRouter envelope routing."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({"data": {"ok": True}})
        mock_router.create_request.return_value = response_future
        
        client = StateQueryClient(mock_router, timeout=5.0)
        await client._send_query("state.query.world", {"key": "val"})
        
        # create_request should be called with some request_id and timeout
        mock_router.create_request.assert_called_once()
        req_id = mock_router.create_request.call_args[0][0]
        
        # publish should pass that same request_id as r kwarg
        mock_router.publish.assert_called_once()
        _, kwargs = mock_router.publish.call_args
        assert kwargs["r"] == req_id
    
    @pytest.mark.asyncio
    async def test_query_publish_failure(self, mock_router):
        """Test handling publish failure."""
        mock_router.publish = AsyncMock(return_value=False)
        mock_router.create_request.return_value = asyncio.get_event_loop().create_future()
        
        client = StateQueryClient(mock_router)
        
        with pytest.raises(ConnectionError, match="Failed to publish"):
            await client._send_query("state.query.memories", {"character_id": "123"})
    
    @pytest.mark.asyncio
    async def test_query_timeout(self, mock_router):
        """Test handling query timeout."""
        future = asyncio.get_event_loop().create_future()
        
        async def timeout_after():
            await asyncio.sleep(0.1)
            if not future.done():
                future.set_exception(TimeoutError("Request timed out"))
        
        asyncio.create_task(timeout_after())
        mock_router.create_request.return_value = future
        
        client = StateQueryClient(mock_router, timeout=0.05)
        
        with pytest.raises(TimeoutError):
            await client._send_query("state.query.memories", {"character_id": "123"})


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
            await client._send_query(
                "state.query.memories",
                {"character_id": "456"}
            )
        
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
            await client._send_query("state.query.world", {})
        
        assert exc_info.value.topic == "state.query.world"
        assert exc_info.value.character_id is None
