"""State query client for requesting game state from Lua via ZMQ."""

import uuid
from typing import Any

from loguru import logger

from .models import MemoryContext, Character, Event, WorldContext


class StateQueryTimeout(TimeoutError):
    """Raised when a state query to Lua times out.
    
    Subclass of TimeoutError so existing ``except TimeoutError`` handlers
    still catch it, while callers that need to distinguish transient
    connectivity failures (e.g. Lua paused in main menu) can catch this
    specific type.
    
    Attributes:
        topic: The ZMQ query topic that timed out (e.g. "state.query.memories").
        character_id: The character_id parameter if the query was character-specific.
    """

    def __init__(
        self,
        message: str = "State query timed out",
        *,
        topic: str | None = None,
        character_id: str | None = None,
    ):
        super().__init__(message)
        self.topic = topic
        self.character_id = character_id


class StateQueryClient:
    """Client for querying game state from Lua via ZMQ.
    
    Uses request/response pattern with request_id correlation.
    Publishes query to Lua, waits for response on state.response topic.
    """
    
    def __init__(self, router, timeout: float = 30.0):
        """Initialize state query client.
        
        Args:
            router: ZMQRouter instance with publish capability
            timeout: Default timeout for queries in seconds
        """
        self.router = router
        self.timeout = timeout
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())
    
    async def _send_query(
        self,
        topic: str,
        params: dict[str, Any],
        timeout: float | None = None
    ) -> dict[str, Any]:
        """Send a query and wait for response.
        
        Args:
            topic: Query topic (e.g., "state.query.memories")
            params: Query parameters
            timeout: Optional timeout override
            
        Returns:
            Response data dict
            
        Raises:
            StateQueryTimeout: If query times out (subclass of TimeoutError)
            ConnectionError: If query cannot be published
        """
        request_id = self._generate_request_id()
        timeout = timeout or self.timeout
        
        # Create pending request future
        future = self.router.create_request(request_id, timeout)
        
        # Build and send query
        payload = {
            "request_id": request_id,
            **params
        }
        
        success = await self.router.publish(topic, payload)
        if not success:
            raise ConnectionError(f"Failed to publish query to {topic}")
        
        logger.debug(f"Sent query {topic} with request_id {request_id}")
        
        # Wait for response
        try:
            response = await future
        except TimeoutError:
            character_id = params.get("character_id")
            raise StateQueryTimeout(
                f"State query timed out: {topic} (request_id={request_id})",
                topic=topic,
                character_id=character_id,
            ) from None
        
        logger.debug(f"Received response for {request_id}")
        
        return response.get("data", response)
    
    async def query_memories(self, character_id: str) -> MemoryContext:
        """Query memory context for a character.
        
        Args:
            character_id: Character game ID
            
        Returns:
            MemoryContext with narrative and new events
        """
        data = await self._send_query(
            "state.query.memories",
            {"character_id": character_id}
        )
        return MemoryContext.from_dict(data)
    
    async def query_events_recent(
        self,
        since_ms: int = 0,
        limit: int = 50
    ) -> list[Event]:
        """Query recent events since a timestamp.
        
        Args:
            since_ms: Game time in milliseconds to query since
            limit: Maximum number of events to return
            
        Returns:
            List of Event objects
        """
        data = await self._send_query(
            "state.query.events",
            {"since_ms": since_ms, "limit": limit}
        )
        
        events = []
        for e in data.get("events", []):
            if isinstance(e, dict):
                events.append(Event.from_dict(e))
        return events
    
    async def query_character(self, character_id: str) -> Character:
        """Query character information by ID.
        
        Args:
            character_id: Character game ID
            
        Returns:
            Character object
        """
        data = await self._send_query(
            "state.query.character",
            {"character_id": character_id}
        )
        return Character.from_dict(data.get("character", data))
    
    async def query_characters_nearby(
        self,
        center_id: str | None = None,
        radius: float = 50.0
    ) -> list[Character]:
        """Query characters near a position or the player.
        
        Args:
            center_id: Optional character ID to center on (defaults to player)
            radius: Search radius in game units
            
        Returns:
            List of Character objects
        """
        params = {"radius": radius}
        if center_id:
            params["center_id"] = center_id
        
        data = await self._send_query(
            "state.query.characters_nearby",
            params
        )
        
        characters = []
        for c in data.get("characters", []):
            if isinstance(c, dict):
                characters.append(Character.from_dict(c))
        return characters
    
    async def query_world_context(self) -> WorldContext:
        """Query current world context (location, time, weather).
        
        Returns:
            WorldContext object
        """
        data = await self._send_query("state.query.world", {})
        return WorldContext.from_dict(data)
