"""WebSocket message schemas for the Lua ↔ Python wire protocol."""

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
    weapon: Optional[str] = None
    visual_faction: Optional[str] = None
    story_id: Optional[str] = None  # Story ID for notable character matching (e.g. "actor")
    sound_prefix: Optional[str] = None  # Voice theme ID, e.g. "stalker_1"

    @model_validator(mode="before")
    @classmethod
    def empty_str_to_none(cls, values: Any) -> Any:
        """Lua sends '' for missing optional strings; normalise to None."""
        if isinstance(values, dict):
            str_fields = {"faction", "experience", "weapon"}
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
    """Game event message from Lua (v2 tool-based format).
    
    New format contains event, candidates list, world context, and traits.
    """
    
    # v2 format fields
    event: Optional[dict[str, Any]] = None          # {type, context, game_time_ms, ...}
    candidates: list[CharacterData] = Field(default_factory=list)  # [Speaker, Witness1, ...]
    world: Optional[str] = None                     # World context string
    traits: Optional[dict[str, dict[str, str]]] = None  # {char_id: {personality_id, backstory_id}, ...}


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


class BatchSubMutation(BaseModel):
    """A single mutation within a batch mutation request."""
    
    id: str
    character_id: str
    verb: str  # append, delete, set, update
    resource: str  # events, summaries, digests, cores, background
    data: Optional[Any] = None
    seq_lte: Optional[int] = None  # For delete verb


class BatchMutationMessage(BaseMessage):
    """Batch mutation request published on ``state.mutate.batch``.
    
    Contains an array of mutations applied to memory tiers.
    """
    
    request_id: str
    mutations: list[BatchSubMutation]


class BatchSubResult(BaseModel):
    """A single result within a batch response."""

    response_type: str  # success, error, not_found
    data: Optional[Any] = None
    error: Optional[str] = None


class BatchResponseMessage(BaseMessage):
    """Batch response received on ``state.response``.

    ``results`` is keyed by the sub-query ``id``.
    """

    request_id: str
    results: dict[str, BatchSubResult]
