"""Data models for state query responses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Character:
    """Character data.
    
    Canonical model for character information throughout the service.
    Mirrors the Lua Character entity structure.
    """
    game_id: str
    name: str
    faction: str = "stalker"
    experience: str = "Experienced"  # Rank
    reputation: int = 0
    weapon: str = ""
    visual_faction: str | None = None  # For disguises
    story_id: str | None = None  # Story ID for notable character matching
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        """Create Character from dict."""
        return cls(
            game_id=str(data.get("game_id", "")),
            name=data.get("name", "Unknown"),
            faction=data.get("faction", "stalker"),
            experience=data.get("experience", "Experienced"),
            reputation=data.get("reputation", 0),
            weapon=data.get("weapon", ""),
            visual_faction=data.get("visual_faction"),
            story_id=data.get("story_id"),
        )


@dataclass
class Event:
    """Event data.
    
    Canonical model for game events throughout the service.
    All events use typed format with `type` and `context` fields.
    """
    game_time_ms: int
    type: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    witnesses: list[Character] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_typed(self) -> bool:
        """Check if this is a typed event."""
        return self.type is not None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create Event from dict.
        
        Note: world_context is intentionally ignored if present in data.
        World context is now queried JIT during prompt building.
        """
        witnesses = []
        for w in data.get("witnesses", []):
            if isinstance(w, dict):
                witnesses.append(Character.from_dict(w))
        
        return cls(
            game_time_ms=data.get("game_time_ms", 0),
            type=data.get("type"),
            context=data.get("context", {}),
            witnesses=witnesses,
            flags=data.get("flags", {}),
        )


@dataclass
class MemoryContext:
    """Memory context for dialogue prompts.
    
    Canonical model for character memory context throughout the service.
    Contains long-term narrative plus recent events.
    """
    narrative: str | None = None
    last_update_time_ms: int = 0
    new_events: list[Event] = field(default_factory=list)
    character_id: str | None = None  # Optional, set when querying for specific character
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryContext":
        """Create MemoryContext from dict."""
        new_events = []
        for e in data.get("new_events", []):
            if isinstance(e, dict):
                new_events.append(Event.from_dict(e))
        
        # character_id may or may not be present
        char_id = data.get("character_id")
        return cls(
            narrative=data.get("narrative"),
            last_update_time_ms=data.get("last_update_time_ms", 0),
            new_events=new_events,
            character_id=str(char_id) if char_id else None,
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


@dataclass
class SceneContext:
    """Enhanced scene context from world.context query.
    
    Contains location, time, weather, and world state info portions.
    """
    loc: str = ""
    poi: str | None = None
    time: dict[str, int] | None = None  # {Y, M, D, h, m, s, ms}
    weather: str = ""
    emission: bool = False
    psy_storm: bool = False
    sheltering: bool = False
    campfire: str | None = None  # "lit" | "unlit" | None
    brain_scorcher_disabled: bool = False
    miracle_machine_disabled: bool = False
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneContext":
        """Create SceneContext from dict."""
        return cls(
            loc=data.get("loc", ""),
            poi=data.get("poi"),
            time=data.get("time"),
            weather=data.get("weather", ""),
            emission=data.get("emission", False),
            psy_storm=data.get("psy_storm", False),
            sheltering=data.get("sheltering", False),
            campfire=data.get("campfire"),
            brain_scorcher_disabled=data.get("brain_scorcher_disabled", False),
            miracle_machine_disabled=data.get("miracle_machine_disabled", False),
        )


@dataclass
class CharactersAliveResponse:
    """Response from characters.alive query.
    
    Maps character story_id to alive status.
    """
    alive_status: dict[str, bool]
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharactersAliveResponse":
        """Create CharactersAliveResponse from dict.
        
        Expects data to be the mapping directly: {"story_id1": true, "story_id2": false}
        """
        # Filter to only include boolean values
        alive_status = {k: bool(v) for k, v in data.items() if isinstance(v, bool)}
        return cls(alive_status=alive_status)
