"""Prompt module for TALKER Service.

Core prompt building functionality for tool-based dialogue.
Legacy modules (bbuilder, helpers) removed in tools-based-memory migration.
"""

from .models import Character, Event, MemoryContext, NarrativeCue
from .factions import (
    get_faction_description,
    get_faction_relation,
    get_faction_relations_text,
    label_faction_relation,
    label_goodwill,
    format_faction_standings,
    format_player_goodwill,
    COMPANION_FACTION_TENSION_NOTE,
    FACTION_RELATION_THRESHOLDS,
    GOODWILL_TIERS,
)

__all__ = [
    # Models (re-exported from state.models + NarrativeCue)
    "Character",
    "Event",
    "MemoryContext",
    "NarrativeCue",
    # Factions
    "get_faction_description",
    "get_faction_relation",
    "get_faction_relations_text",
    # Dynamic faction data
    "label_faction_relation",
    "label_goodwill",
    "format_faction_standings",
    "format_player_goodwill",
    "COMPANION_FACTION_TENSION_NOTE",
    "FACTION_RELATION_THRESHOLDS",
    "GOODWILL_TIERS",
]
