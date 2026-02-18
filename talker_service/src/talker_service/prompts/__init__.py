"""Prompt builder module for TALKER Service.

Ports prompt building logic from Lua to Python for:
- Dialogue generation
- Speaker selection  
- Memory compression
- Narrative updates
"""

from .models import Character, Event, MemoryContext, NarrativeCue
from .builder import (
    Message,
    create_dialogue_request_prompt,
    create_pick_speaker_prompt,
    create_compress_memories_prompt,
    create_update_narrative_prompt,
    create_transcription_prompt,
)
from .helpers import (
    describe_character,
    describe_character_with_id,
    describe_event,
    is_junk_event,
    was_witnessed_by,
    inject_time_gaps,
)
from .factions import (
    get_faction_description,
    get_faction_relation,
    get_faction_relations_text,
)

__all__ = [
    # Models
    "Character",
    "Event",
    "MemoryContext",
    "NarrativeCue",
    "Message",
    # Helpers
    "describe_character",
    "describe_character_with_id",
    "describe_event",
    "is_junk_event",
    "was_witnessed_by",
    "inject_time_gaps",
    # Factions
    "get_faction_description",
    "get_faction_relation",
    "get_faction_relations_text",
    # Prompt builders
    "create_dialogue_request_prompt",
    "create_pick_speaker_prompt",
    "create_compress_memories_prompt",
    "create_update_narrative_prompt",
    "create_transcription_prompt",
]
