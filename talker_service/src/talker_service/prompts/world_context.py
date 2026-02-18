"""World context builder for dialogue prompts.

Provides queries and builders for dynamic world state context
including dead faction leaders, major world events, and regional politics.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict

from loguru import logger

from talker_service.prompts.factions import resolve_faction_name

if TYPE_CHECKING:
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


def _get_all_story_ids() -> List[str]:
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


async def query_characters_alive(
    state_client: "StateQueryClient",
    ids: list[str],
) -> dict[str, bool]:
    """Query Lua for alive/dead status of specified characters.
    
    Args:
        state_client: StateQueryClient instance
        ids: List of character story_ids to check
        
    Returns:
        Dict mapping story_id to alive status (True=alive, False=dead)
    """
    if not ids:
        return {}
    
    try:
        # Use _send_query directly for custom query type
        data = await state_client._send_query(
            "state.query",
            {"type": "characters.alive", "ids": ids},
        )
        
        # Response should be a dict mapping id to boolean
        result = {}
        for id_ in ids:
            result[id_] = bool(data.get(id_, False))
        return result
        
    except Exception as e:
        logger.error(f"Failed to query characters alive: {e}")
        # Return all as alive on error (safe default)
        return {id_: True for id_ in ids}


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
    state_client: "StateQueryClient",
    recent_events: list | None = None,
) -> str:
    """Build complete world context section for dialogue prompts.
    
    Aggregates all context sections:
    - Dead faction leaders
    - Dead important characters
    - Info portions (Brain Scorcher, Miracle Machine)
    - Regional politics
    
    Args:
        scene_data: SceneContext from world.context query
        state_client: StateQueryClient for character alive queries
        recent_events: Optional list of recent events
        
    Returns:
        Combined world context text, or empty string if nothing notable
    """
    sections = []
    
    # Get character IDs filtered by current area
    current_area = scene_data.loc if scene_data else ""
    relevant_ids = _get_story_ids_for_area(current_area)
    
    # Query alive status for relevant characters only
    alive_status = await query_characters_alive(state_client, relevant_ids)
    
    # Build dead leaders section
    dead_leaders = build_dead_leaders_context(alive_status)
    if dead_leaders:
        sections.append(dead_leaders)
    
    # Build dead important characters section
    current_area = scene_data.loc if scene_data else ""
    dead_important = build_dead_important_context(
        alive_status,
        current_area=current_area,
        recent_events=recent_events,
    )
    if dead_important:
        sections.append(dead_important)
    
    # Build info portions section
    if scene_data:
        info_portions = build_info_portions_context(scene_data)
        if info_portions:
            sections.append(info_portions)
    
    # Build regional politics section
    regional = build_regional_context(current_area)
    if regional:
        sections.append(regional)
    
    return "\n\n".join(sections)
