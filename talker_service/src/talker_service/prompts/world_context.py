"""World context builder for dialogue prompts.

Provides queries and builders for dynamic world state context
including dead faction leaders, major world events, and regional politics.
"""

from dataclasses import dataclass, field
from importlib import import_module
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict

from loguru import logger

from talker_service.prompts.factions import (
    resolve_faction_name,
    format_faction_standings,
    format_player_goodwill,
)

if TYPE_CHECKING:
    from ..dialogue.context_block import ContextBlock
    from ..state.client import StateQueryClient
    from ..state.models import SceneContext


# Type definition for character entries
class ImportantCharacter(TypedDict, total=False):
    """Character entry in the important characters registry."""
    ids: List[str]
    name: str
    names: List[str]
    role: str
    faction: str
    area: str
    areas: List[str]
    description: str


# Module cache for characters
_characters_module: Optional[object] = None


def _get_characters() -> List[ImportantCharacter]:
    """Get CHARACTERS list from texts.characters.important module."""
    global _characters_module
    if _characters_module is None:
        try:
            _characters_module = import_module("texts.characters.important")
        except ImportError:
            logger.error("Failed to import texts.characters.important")
            return []
    return getattr(_characters_module, "CHARACTERS", [])


def _get_leaders() -> List[ImportantCharacter]:
    """Get all faction leader characters."""
    return [c for c in _get_characters() if c.get("role") == "leader"]


def _get_important() -> List[ImportantCharacter]:
    """Get all important (non-leader) characters."""
    return [c for c in _get_characters() if c.get("role") == "important"]


def _get_notable() -> List[ImportantCharacter]:
    """Get all notable characters."""
    return [c for c in _get_characters() if c.get("role") == "notable"]


def _extract_story_ids_from_events(events: list) -> set[str]:
    """Extract all story_ids from event witnesses and context characters.
    
    Args:
        events: List of Event objects
        
    Returns:
        Set of story_ids found in witnesses and context
    """
    story_ids: set[str] = set()
    
    for event in events:
        # Extract from witnesses
        witnesses = getattr(event, "witnesses", [])
        for witness in witnesses:
            story_id = getattr(witness, "story_id", None)
            if story_id:
                story_ids.add(story_id)
        
        # Extract from context (character fields vary by event type)
        context = getattr(event, "context", {})
        if isinstance(context, dict):
            for key in ("actor", "victim", "target", "killer", "speaker"):
                char = context.get(key)
                if isinstance(char, dict):
                    story_id = char.get("story_id")
                    if story_id:
                        story_ids.add(story_id)
    
    return story_ids


def _is_notable_relevant(
    char: ImportantCharacter,
    current_area: str,
    recent_events: list | None,
) -> bool:
    """Check if a notable character is contextually relevant.
    
    Returns True if any of these criteria match:
    1. Character's story_id appears in recent event witnesses/context
    2. Current location matches character's area
    
    Args:
        char: Notable character entry
        current_area: Technical location ID (e.g., "l01_escape")
        recent_events: List of recent events (optional)
        
    Returns:
        True if character is relevant to current context
    """
    # Get character data
    char_area = char.get("area", "")
    char_areas = char.get("areas", [])
    char_ids = set(char.get("ids", []))
    
    # Criterion 1: Character's story_id in event witnesses/context
    if recent_events and char_ids:
        event_story_ids = _extract_story_ids_from_events(recent_events)
        if char_ids & event_story_ids:  # Set intersection
            return True
    
    # Criterion 2: Current location matches character's area (technical IDs)
    if current_area:
        current_lower = current_area.lower()
        if char_area and char_area.lower() == current_lower:
            return True
        for area in char_areas:
            if area.lower() == current_lower:
                return True
    
    return False


def get_all_story_ids() -> List[str]:
    """Get all story IDs from all characters (flattened)."""
    ids = []
    for char in _get_characters():
        ids.extend(char.get("ids", []))
    return ids


def _get_story_ids_for_area(current_area: str) -> List[str]:
    """Get story IDs filtered by area relevance.
    
    Returns:
        - All leader IDs (globally important)
        - IDs for characters in the current area
        - IDs for characters with no area restriction
    
    Args:
        current_area: Technical location ID (e.g., "l01_escape")
        
    Returns:
        List of story IDs relevant to the area
    """
    ids = []
    current_lower = current_area.lower() if current_area else ""
    
    for char in _get_characters():
        role = char.get("role", "")
        
        # Leaders: always include (globally important)
        if role == "leader":
            ids.extend(char.get("ids", []))
            continue
        
        # Check area/areas fields (technical IDs)
        char_area = char.get("area", "")
        char_areas = char.get("areas", [])
        
        # No area restriction: always include
        if not char_area and not char_areas:
            ids.extend(char.get("ids", []))
            continue
        
        # Check if current area matches (compare technical IDs directly)
        if current_lower:
            if char_area and char_area.lower() == current_lower:
                ids.extend(char.get("ids", []))
            elif char_areas and any(a.lower() == current_lower for a in char_areas):
                ids.extend(char.get("ids", []))
    
    return ids




def build_dead_leaders_context(alive_status: dict[str, bool]) -> str:
    """Generate prompt text for dead faction leaders.
    
    Args:
        alive_status: Dict mapping story_id to alive status
        
    Returns:
        Formatted text listing dead leaders, or empty string if none
    """
    dead_lines = []
    
    for leader in _get_leaders():
        # Check if any of this leader's IDs show dead
        is_dead = False
        for id_ in leader.get("ids", []):
            if id_ in alive_status and not alive_status[id_]:
                is_dead = True
                break
        
        if is_dead:
            name = leader.get("name", "Unknown")
            faction = resolve_faction_name(leader.get("faction", "unknown"))
            description = leader.get("description", "")
            
            if description:
                dead_lines.append(f"{name}, {description}, is dead.")
            else:
                dead_lines.append(f"{name}, leader of {faction}, is dead.")
    
    return "\n".join(dead_lines)


def build_dead_important_context(
    alive_status: dict[str, bool],
    current_area: str = "",
    recent_events: list | None = None,
) -> str:
    """Generate prompt text for dead important characters (non-leaders).
    
    Notable characters are filtered by area - only shown if player is in
    the character's associated area.
    
    Args:
        alive_status: Dict mapping story_id to alive status
        current_area: Current location ID (e.g., "l01_escape")
        recent_events: Optional list of recent events for context filtering
        
    Returns:
        Formatted text listing dead important characters, or empty string
    """
    dead_lines = []
    
    # Process important characters (always shown if dead)
    for char in _get_important():
        is_dead = False
        for id_ in char.get("ids", []):
            if id_ in alive_status and not alive_status[id_]:
                is_dead = True
                break
        
        if is_dead:
            name = char.get("name", "Unknown")
            description = char.get("description", "")
            
            if description:
                dead_lines.append(f"{name}, {description}, is dead.")
            else:
                faction = resolve_faction_name(char.get("faction", ""))
                if faction:
                    dead_lines.append(f"{name} of {faction} is dead.")
                else:
                    dead_lines.append(f"{name} is dead.")
    
    # Process notable characters (filtered by 3 criteria: name in events, area in events, location match)
    for char in _get_notable():
        # Skip if not contextually relevant (pass technical ID directly)
        if not _is_notable_relevant(char, current_area, recent_events):
            continue
        
        is_dead = False
        for id_ in char.get("ids", []):
            if id_ in alive_status and not alive_status[id_]:
                is_dead = True
                break
        
        if is_dead:
            name = char.get("name", "Unknown")
            description = char.get("description", "")
            
            if description:
                dead_lines.append(f"{name}, {description}, is dead.")
            else:
                dead_lines.append(f"{name} is dead.")
    
    return "\n".join(dead_lines)


def build_inhabitants_context(
    alive_status: dict[str, bool],
    current_area: str = "",
    recent_events: list | None = None,
) -> str:
    """Generate prompt text for notable zone inhabitants (alive and dead).
    
    Lists characterized NPCs relevant to the current context with alive/dead status.
    
    Filtering logic:
    - Leaders: always included (globally important)
    - Important: always included (major story characters)
    - Notable: included only if contextually relevant (area match or event mention)
    
    Args:
        alive_status: Dict mapping story_id to alive status
        current_area: Current location ID (e.g., "l01_escape")
        recent_events: Optional list of recent events for context filtering
        
    Returns:
        Formatted text listing inhabitants with status, or empty string if none
    """
    inhabitants_lines = []
    
    # Process leaders (always included)
    for leader in _get_leaders():
        name = leader.get("name", "Unknown")
        description = leader.get("description", "")
        faction = resolve_faction_name(leader.get("faction", "unknown"))
        
        # Check alive/dead status
        is_dead = False
        for id_ in leader.get("ids", []):
            if id_ in alive_status and not alive_status[id_]:
                is_dead = True
                break
        
        status = "dead" if is_dead else "alive"
        
        if description:
            inhabitants_lines.append(f"- {name}, {description} ({status})")
        else:
            inhabitants_lines.append(f"- {name}, leader of {faction} ({status})")
    
    # Process important characters (always included if have a description or area match)
    for char in _get_important():
        name = char.get("name", "Unknown")
        description = char.get("description", "")
        faction = resolve_faction_name(char.get("faction", ""))
        
        # Check alive/dead status
        is_dead = False
        for id_ in char.get("ids", []):
            if id_ in alive_status and not alive_status[id_]:
                is_dead = True
                break
        
        status = "dead" if is_dead else "alive"
        
        if description:
            inhabitants_lines.append(f"- {name}, {description} ({status})")
        else:
            if faction:
                inhabitants_lines.append(f"- {name}, {faction} ({status})")
            else:
                inhabitants_lines.append(f"- {name} ({status})")
    
    # Process notable characters (filtered by relevance)
    for char in _get_notable():
        # Skip if not contextually relevant
        if not _is_notable_relevant(char, current_area, recent_events):
            continue
        
        name = char.get("name", "Unknown")
        description = char.get("description", "")
        faction = resolve_faction_name(char.get("faction", ""))
        
        # Check alive/dead status
        is_dead = False
        for id_ in char.get("ids", []):
            if id_ in alive_status and not alive_status[id_]:
                is_dead = True
                break
        
        status = "dead" if is_dead else "alive"
        
        if description:
            inhabitants_lines.append(f"- {name}, {description} ({status})")
        else:
            if faction:
                inhabitants_lines.append(f"- {name}, {faction} ({status})")
            else:
                inhabitants_lines.append(f"- {name} ({status})")
    
    # Return empty string if no inhabitants to list
    if not inhabitants_lines:
        return ""
    
    return "**Notable Zone Inhabitants:**\n" + "\n".join(inhabitants_lines)


def build_info_portions_context(scene_data: "SceneContext") -> str:
    """Generate prompt text for major world events from info portions.
    
    Args:
        scene_data: SceneContext with brain_scorcher_disabled, miracle_machine_disabled
        
    Returns:
        Formatted text about disabled installations, or empty string
    """
    lines = []
    
    if scene_data.brain_scorcher_disabled:
        lines.append(
            "The Brain Scorcher in Radar has been disabled again, "
            "opening the path to the North."
        )
    
    if scene_data.miracle_machine_disabled:
        lines.append("The Miracle Machine in Yantar has been disabled again.")
    
    return "\n".join(lines)


def build_regional_context(current_area: str) -> str:
    """Generate context-specific political information.
    
    Args:
        current_area: Current location ID (e.g., "l01_escape")
        
    Returns:
        Regional political context, or empty string if none
    """
    # Cordon truce
    if current_area and "l01_escape" in current_area.lower():
        return (
            "The Military and Loners have an uneasy truce in Cordon. "
            "The Military controls the southern checkpoint but allows "
            "stalkers through as long as they don't cause trouble."
        )
    
    return ""


async def build_world_context(
    scene_data: "SceneContext",
    recent_events: list | None = None,
    alive_status: dict[str, bool] | None = None,
) -> str:
    """Build complete world context section for dialogue prompts.
    
    Aggregates all context sections:
    - Notable zone inhabitants (leaders, important, and contextually relevant notable NPCs)
    - Info portions (Brain Scorcher, Miracle Machine)
    - Regional politics
    
    Args:
        scene_data: SceneContext from world.context query
        recent_events: Optional list of recent events
        alive_status: Pre-fetched alive status dict from batch query
        
    Returns:
        Combined world context text, or empty string if nothing notable
    """
    sections = []
    
    # Get character IDs filtered by current area
    current_area = scene_data.loc if scene_data else ""
    
    if alive_status is None:
        alive_status = {}
    
    # Build inhabitants section (replaces dead leaders + dead important sections)
    inhabitants = build_inhabitants_context(
        alive_status,
        current_area=current_area,
        recent_events=recent_events,
    )
    if inhabitants:
        sections.append(inhabitants)
    
    # Build info portions section
    if scene_data:
        info_portions = build_info_portions_context(scene_data)
        if info_portions:
            sections.append(info_portions)
    
    # Build regional politics section
    regional = build_regional_context(current_area)
    if regional:
        sections.append(regional)
    
    # Build faction standings section
    if scene_data and scene_data.faction_standings:
        standings_text = format_faction_standings(scene_data.faction_standings)
        if standings_text:
            sections.append(f"Faction standings:\n{standings_text}")
    
    # Build player goodwill section
    if scene_data and scene_data.player_goodwill:
        goodwill_text = format_player_goodwill(scene_data.player_goodwill)
        if goodwill_text:
            sections.append(f"Player goodwill:\n{goodwill_text}")
    
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Structured world context (split for cache-friendly prompt layout)
# ---------------------------------------------------------------------------

@dataclass
class InhabitantEntry:
    """A notable Zone inhabitant for context block injection."""
    char_id: str
    name: str
    faction: str
    description: str


@dataclass
class WorldContextSplit:
    """Structured world context separating static and dynamic items.

    Static items go into the ``ContextBlock`` (``_messages[1]``).
    Dynamic items go into per-turn user instruction messages (Layer 4).
    """
    # Static items (for context block / _messages[1])
    inhabitants: list[InhabitantEntry] = field(default_factory=list)
    faction_standings: str = ""
    player_goodwill: str = ""
    info_portions: str = ""

    # Dynamic items (for per-turn instruction messages)
    weather: str = ""
    time_of_day: str = ""
    location: str = ""
    regional_context: str = ""


def build_world_context_split(
    scene_data: "SceneContext",
    recent_events: list | None = None,
    alive_status: dict[str, bool] | None = None,
) -> WorldContextSplit:
    """Build structured world context separating static from dynamic items.

    Static items (inhabitants, factions, info portions) are destined for the
    context block.  Dynamic items (weather, time, location) go into per-turn
    instruction messages.

    Args:
        scene_data: SceneContext from world.context query
        recent_events: Optional list of recent events
        alive_status: Pre-fetched alive status dict from batch query

    Returns:
        WorldContextSplit with separated static and dynamic fields.
    """
    if alive_status is None:
        alive_status = {}

    result = WorldContextSplit()
    current_area = scene_data.loc if scene_data else ""

    # --- Static: Inhabitants ---
    result.inhabitants = _build_inhabitant_entries(
        alive_status, current_area, recent_events,
    )

    # --- Static: Info portions ---
    if scene_data:
        result.info_portions = build_info_portions_context(scene_data)

    # --- Static: Faction standings ---
    if scene_data and scene_data.faction_standings:
        standings = format_faction_standings(scene_data.faction_standings)
        if standings:
            result.faction_standings = f"Faction standings:\n{standings}"

    # --- Static: Player goodwill ---
    if scene_data and scene_data.player_goodwill:
        goodwill = format_player_goodwill(scene_data.player_goodwill)
        if goodwill:
            result.player_goodwill = f"Player goodwill:\n{goodwill}"

    # --- Dynamic: Weather ---
    if scene_data and scene_data.weather:
        result.weather = scene_data.weather

    # --- Dynamic: Time ---
    if scene_data and scene_data.time:
        t = scene_data.time
        h = t.get("h", 0)
        m = t.get("m", 0)
        result.time_of_day = f"{h:02d}:{m:02d}"

    # --- Dynamic: Location ---
    if current_area:
        result.location = current_area

    # --- Dynamic: Regional context ---
    result.regional_context = build_regional_context(current_area)

    return result


def _build_inhabitant_entries(
    alive_status: dict[str, bool],
    current_area: str = "",
    recent_events: list | None = None,
) -> list[InhabitantEntry]:
    """Build inhabitant entries for context block injection.

    Returns list of InhabitantEntry for leaders, important, and relevant
    notable characters with alive/dead status annotation.
    """
    entries: list[InhabitantEntry] = []

    # Leaders (always included)
    for leader in _get_leaders():
        name = leader.get("name", "Unknown")
        description = leader.get("description", "")
        faction = resolve_faction_name(leader.get("faction", "unknown"))

        is_dead = any(
            id_ in alive_status and not alive_status[id_]
            for id_ in leader.get("ids", [])
        )
        status = "dead" if is_dead else "alive"
        desc = f"{description} ({status})" if description else f"leader of {faction} ({status})"

        # Use first ID as char_id
        char_id = leader.get("ids", [""])[0] if leader.get("ids") else ""
        if char_id:
            entries.append(InhabitantEntry(char_id=char_id, name=name, faction=faction, description=desc))

    # Important characters (always included)
    for char in _get_important():
        name = char.get("name", "Unknown")
        description = char.get("description", "")
        faction = resolve_faction_name(char.get("faction", ""))

        is_dead = any(
            id_ in alive_status and not alive_status[id_]
            for id_ in char.get("ids", [])
        )
        status = "dead" if is_dead else "alive"

        if description:
            desc = f"{description} ({status})"
        elif faction:
            desc = f"{faction} ({status})"
        else:
            desc = f"({status})"

        char_id = char.get("ids", [""])[0] if char.get("ids") else ""
        if char_id:
            entries.append(InhabitantEntry(char_id=char_id, name=name, faction=faction or "Unknown", description=desc))

    # Notable characters (filtered by relevance)
    for char in _get_notable():
        if not _is_notable_relevant(char, current_area, recent_events):
            continue

        name = char.get("name", "Unknown")
        description = char.get("description", "")
        faction = resolve_faction_name(char.get("faction", ""))

        is_dead = any(
            id_ in alive_status and not alive_status[id_]
            for id_ in char.get("ids", [])
        )
        status = "dead" if is_dead else "alive"

        if description:
            desc = f"{description} ({status})"
        elif faction:
            desc = f"{faction} ({status})"
        else:
            desc = f"({status})"

        char_id = char.get("ids", [""])[0] if char.get("ids") else ""
        if char_id:
            entries.append(InhabitantEntry(char_id=char_id, name=name, faction=faction or "Unknown", description=desc))

    return entries


def add_inhabitants_to_context_block(
    context_block: "ContextBlock",
    inhabitants: list[InhabitantEntry],
) -> int:
    """Add inhabitant entries to a ContextBlock as background items.

    Args:
        context_block: The ContextBlock to add items to.
        inhabitants: List of InhabitantEntry from build_world_context_split.

    Returns:
        Number of items actually added (non-duplicates).
    """
    added = 0
    for entry in inhabitants:
        if context_block.add_background(entry.char_id, entry.name, entry.faction, entry.description):
            added += 1
    return added


def add_static_context_to_block(
    context_block: "ContextBlock",
    world_split: WorldContextSplit,
) -> None:
    """Add all static world context items to a ContextBlock.

    Adds inhabitants as background entries and faction standings / info
    portions / player goodwill as special background entries with synthetic IDs.

    Args:
        context_block: The ContextBlock to add items to.
        world_split: WorldContextSplit from build_world_context_split.
    """
    # Add inhabitants
    add_inhabitants_to_context_block(context_block, world_split.inhabitants)

    # Add faction standings as a special entry
    if world_split.faction_standings:
        context_block.add_background(
            "__faction_standings__", "Faction Relations", "Zone",
            world_split.faction_standings,
        )

    # Add player goodwill as a special entry
    if world_split.player_goodwill:
        context_block.add_background(
            "__player_goodwill__", "Player Reputation", "Zone",
            world_split.player_goodwill,
        )

    # Add info portions as a special entry
    if world_split.info_portions:
        context_block.add_background(
            "__info_portions__", "Major World Events", "Zone",
            world_split.info_portions,
        )


def build_dynamic_world_line(world_split: WorldContextSplit) -> str:
    """Build a single-line summary of dynamic world state for per-turn injection.

    Args:
        world_split: WorldContextSplit from build_world_context_split.

    Returns:
        String like "Location: Garbage. Time: 14:35. Weather: Clear."
        or empty string if no dynamic data.
    """
    parts: list[str] = []
    if world_split.location:
        parts.append(f"Location: {world_split.location}")
    if world_split.time_of_day:
        parts.append(f"Time: {world_split.time_of_day}")
    if world_split.weather:
        parts.append(f"Weather: {world_split.weather}")
    if world_split.regional_context:
        parts.append(world_split.regional_context)
    return ". ".join(parts) + "." if parts else ""
