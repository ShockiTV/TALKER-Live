"""ZMQ message schemas."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


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
    reputation: int = 0
    personality: Optional[str] = None
    backstory: Optional[str] = None
    weapon: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def empty_str_to_none(cls, values: Any) -> Any:
        """Lua sends '' for missing optional strings; normalise to None."""
        if isinstance(values, dict):
            str_fields = {"faction", "experience", "personality", "backstory", "weapon"}
            for field in str_fields:
                if values.get(field) == "":
                    values[field] = None
        return values


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


# --- Batch Query wire-format schemas ---


class BatchSubQuery(BaseModel):
    """A single sub-query within a batch request.

    Mirrors the JSON structure sent over ZMQ to Lua's
    ``state.query.batch`` handler.
    """

    id: str
    resource: str
    params: Optional[dict[str, Any]] = None
    filter: Optional[dict[str, Any]] = None
    sort: Optional[dict[str, int]] = None
    limit: Optional[int] = None
    fields: Optional[list[str]] = None


class BatchQueryMessage(BaseMessage):
    """Batch query request published on ``state.query.batch``.

    Contains an array of sub-queries executed sequentially on the Lua
    side with ``$ref`` cross-query resolution.
    """

    request_id: str
    queries: list[BatchSubQuery]


class BatchSubResult(BaseModel):
    """Result for a single sub-query within a batch response."""

    ok: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class BatchResponseMessage(BaseMessage):
    """Batch response received on ``state.response``.

    ``results`` is keyed by the sub-query ``id``.
    """

    request_id: str
    results: dict[str, BatchSubResult]
