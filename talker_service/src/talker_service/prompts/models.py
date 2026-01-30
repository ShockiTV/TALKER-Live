"""Data models for prompts."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Character:
    """Character data for prompts.
    
    Mirrors the Lua Character entity structure.
    """
    game_id: str
    name: str
    faction: str = "stalker"
    experience: str = "Experienced"  # Rank
    reputation: str = "Neutral"
    personality: str = ""
    backstory: str = ""
    weapon: str = ""
    visual_faction: str | None = None  # For disguises
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        """Create from dictionary (e.g., from ZMQ payload)."""
        return cls(
            game_id=str(data.get("game_id", "")),
            name=data.get("name", "Unknown"),
            faction=data.get("faction", "stalker"),
            experience=data.get("experience", "Experienced"),
            reputation=data.get("reputation", "Neutral"),
            personality=data.get("personality", ""),
            backstory=data.get("backstory", ""),
            weapon=data.get("weapon", ""),
            visual_faction=data.get("visual_faction"),
        )


@dataclass
class Event:
    """Event data for prompts.
    
    Supports both typed events (with type/context) and legacy events (with content).
    """
    game_time_ms: int
    type: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    content: str | None = None  # Legacy format
    world_context: str = ""
    witnesses: list[Character] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create from dictionary (e.g., from ZMQ payload)."""
        witnesses = []
        for w in data.get("witnesses", []):
            if isinstance(w, dict):
                witnesses.append(Character.from_dict(w))
        
        return cls(
            game_time_ms=data.get("game_time_ms", 0),
            type=data.get("type"),
            context=data.get("context", {}),
            content=data.get("content"),
            world_context=data.get("world_context", ""),
            witnesses=witnesses,
            flags=data.get("flags", {}),
        )
    
    @property
    def is_typed(self) -> bool:
        """Check if this is a typed event (vs legacy content-based)."""
        return self.type is not None
    
    @property
    def is_synthetic(self) -> bool:
        """Check if this is a synthetic/compressed event."""
        return self.flags.get("is_synthetic", False) or self.flags.get("is_compressed", False)


@dataclass
class MemoryContext:
    """Memory context for dialogue prompts.
    
    Contains long-term narrative plus recent events.
    """
    narrative: str | None = None
    last_update_time_ms: int = 0
    new_events: list[Event] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryContext":
        """Create from dictionary."""
        events = []
        for e in data.get("new_events", []):
            if isinstance(e, dict):
                events.append(Event.from_dict(e))
        
        return cls(
            narrative=data.get("narrative"),
            last_update_time_ms=data.get("last_update_time_ms", 0),
            new_events=events,
        )
