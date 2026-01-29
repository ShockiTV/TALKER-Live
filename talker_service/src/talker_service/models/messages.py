"""ZMQ message schemas."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    """Base class for all ZMQ messages."""
    
    topic: Optional[str] = None
    timestamp: Optional[int] = None  # Unix timestamp in milliseconds


class CharacterData(BaseModel):
    """Serialized character data from Lua."""
    
    game_id: int | str
    name: str
    faction: Optional[str] = None
    experience: Optional[str] = None  # Rank name
    reputation: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None
    weapon: Optional[str] = None


class EventContext(BaseModel):
    """Context data for a game event."""
    
    actor: Optional[CharacterData] = None
    victim: Optional[CharacterData] = None
    text: Optional[str] = None
    item_name: Optional[str] = None
    action: Optional[str] = None
    # Allow additional fields
    model_config = {"extra": "allow"}


class GameEventMessage(BaseMessage):
    """Game event message from Lua (typed event structure)."""
    
    type: Optional[str] = None  # EventType enum value (DEATH, DIALOGUE, etc.)
    context: Optional[EventContext | dict] = None  # Event-specific context
    game_time_ms: Optional[int] = None
    world_context: Optional[str] = None  # Location/time description
    witnesses: list[CharacterData] = Field(default_factory=list)
    flags: Optional[dict[str, Any] | list] = None  # Lua empty table can be [] or {}
    
    def get_flags(self) -> dict[str, Any]:
        """Get flags as dict, handling Lua's empty table serialization."""
        if self.flags is None or isinstance(self.flags, list):
            return {}
        return self.flags


class PlayerDialogueMessage(BaseMessage):
    """Player dialogue input message."""
    
    text: str
    context: Optional[dict[str, Any]] = None


class ConfigMessage(BaseMessage):
    """MCM configuration message."""
    
    # All config values are passed as a flat dict
    # We use extra="allow" to accept any MCM settings
    model_config = {"extra": "allow"}


class HeartbeatMessage(BaseMessage):
    """Heartbeat message from Lua."""
    
    alive: bool = True
    game_time_ms: Optional[int] = None
