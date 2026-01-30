"""Data models for state query responses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Character:
    """Character data returned from Lua."""
    game_id: str
    name: str
    faction: str = ""
    experience: str = ""  # Rank
    reputation: str = ""
    personality: str = ""
    backstory: str = ""
    weapon: str = ""
    visual_faction: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        """Create Character from dict."""
        return cls(
            game_id=str(data.get("game_id", "")),
            name=data.get("name", "Unknown"),
            faction=data.get("faction", ""),
            experience=data.get("experience", ""),
            reputation=data.get("reputation", ""),
            personality=data.get("personality", ""),
            backstory=data.get("backstory", ""),
            weapon=data.get("weapon", ""),
            visual_faction=data.get("visual_faction"),
        )


@dataclass
class Event:
    """Event data returned from Lua."""
    type: str | None = None
    content: str | None = None  # Legacy format
    context: dict[str, Any] = field(default_factory=dict)
    game_time_ms: int = 0
    world_context: str = ""
    witnesses: list[Character] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create Event from dict."""
        witnesses = []
        for w in data.get("witnesses", []):
            if isinstance(w, dict):
                witnesses.append(Character.from_dict(w))
        
        return cls(
            type=data.get("type"),
            content=data.get("content"),
            context=data.get("context", {}),
            game_time_ms=data.get("game_time_ms", 0),
            world_context=data.get("world_context", ""),
            witnesses=witnesses,
            flags=data.get("flags", {}),
        )


@dataclass
class MemoryContext:
    """Memory context for a character."""
    character_id: str
    narrative: str | None = None
    last_update_time_ms: int = 0
    new_events: list[Event] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryContext":
        """Create MemoryContext from dict."""
        new_events = []
        for e in data.get("new_events", []):
            if isinstance(e, dict):
                new_events.append(Event.from_dict(e))
        
        return cls(
            character_id=str(data.get("character_id", "")),
            narrative=data.get("narrative"),
            last_update_time_ms=data.get("last_update_time_ms", 0),
            new_events=new_events,
        )


@dataclass
class WorldContext:
    """Current world state context."""
    location: str = ""
    location_technical: str = ""
    nearby_smart_terrain: str | None = None
    time_of_day: str = ""
    weather: str = ""
    emission: str = ""
    game_time_ms: int = 0
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldContext":
        """Create WorldContext from dict."""
        return cls(
            location=data.get("location", ""),
            location_technical=data.get("location_technical", ""),
            nearby_smart_terrain=data.get("nearby_smart_terrain"),
            time_of_day=data.get("time_of_day", ""),
            weather=data.get("weather", ""),
            emission=data.get("emission", ""),
            game_time_ms=data.get("game_time_ms", 0),
        )
