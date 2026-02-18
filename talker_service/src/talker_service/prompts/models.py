"""Data models for prompts.

Imports canonical models from state.models and adds prompt-specific models.
"""

from dataclasses import dataclass

# Import canonical models from state - single source of truth
from ..state.models import Character, Event, MemoryContext

# Re-export for convenience
__all__ = ["Character", "Event", "MemoryContext", "NarrativeCue"]


@dataclass
class NarrativeCue:
    """Transient prompt-building artifact (NOT stored in event_store).
    
    Used for injecting contextual markers into prompts, such as time gaps.
    These are only used during prompt construction and never persisted.
    """
    type: str  # "TIME_GAP", future: "LOCATION_CHANGE", etc.
    message: str
    game_time_ms: int  # For sorting with events
    
    @property
    def is_cue(self) -> bool:
        """Always True - distinguishes from Event."""
        return True
