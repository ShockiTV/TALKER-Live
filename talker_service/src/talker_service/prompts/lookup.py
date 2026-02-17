"""Lookup module for resolving IDs to text.

Central location for ID→text resolution functions:
- resolve_personality: personality ID → text
- resolve_backstory: backstory ID → text
- resolve_faction_name: technical faction ID → display name

Uses Python dict constants from text modules. Files are stored as:
  texts/personality/{faction}.py (exports TEXTS dict)
  texts/backstory/{faction}.py (exports TEXTS dict)
"""

from importlib import import_module
from typing import Dict

from loguru import logger

# Re-export resolve_faction_name for central access
from talker_service.prompts.factions import resolve_faction_name


# Module cache: faction name -> module with TEXTS dict
_personality_modules: Dict[str, object] = {}
_backstory_modules: Dict[str, object] = {}


def _get_personality_module(faction: str) -> Dict[str, str]:
    """Get personality TEXTS dict for a faction, with caching."""
    if faction not in _personality_modules:
        try:
            module = import_module(f"texts.personality.{faction}")
            _personality_modules[faction] = getattr(module, 'TEXTS', {})
        except ImportError:
            logger.debug(f"No personality module for faction: {faction}")
            _personality_modules[faction] = {}
    return _personality_modules[faction]


def _get_backstory_module(faction: str) -> Dict[str, str]:
    """Get backstory TEXTS dict for a faction, with caching."""
    if faction not in _backstory_modules:
        try:
            module = import_module(f"texts.backstory.{faction}")
            _backstory_modules[faction] = getattr(module, 'TEXTS', {})
        except ImportError:
            logger.debug(f"No backstory module for faction: {faction}")
            _backstory_modules[faction] = {}
    return _backstory_modules[faction]


def resolve_personality(personality_id: str) -> str:
    """Resolve personality ID to text.
    
    Args:
        personality_id: ID in format "{faction}.{key}" (e.g., "bandit.3", "unique.devushka")
    
    Returns:
        Personality text, or empty string if not found
    """
    if not personality_id or "." not in personality_id:
        return ""
    
    faction, key = personality_id.split(".", 1)
    texts = _get_personality_module(faction)
    return texts.get(key, "")


def resolve_backstory(backstory_id: str) -> str:
    """Resolve backstory ID to text.
    
    Args:
        backstory_id: ID in format "{faction}.{key}" (e.g., "loner.3", "unique.wolf")
    
    Returns:
        Backstory text, or empty string if not found
    """
    if not backstory_id or "." not in backstory_id:
        return ""
    
    faction, key = backstory_id.split(".", 1)
    texts = _get_backstory_module(faction)
    return texts.get(key, "")


def clear_cache() -> None:
    """Clear the module cache. Useful for testing."""
    _personality_modules.clear()
    _backstory_modules.clear()

