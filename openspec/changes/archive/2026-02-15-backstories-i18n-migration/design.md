# Backstories Text Lookup Migration - Design

## Overview

Move backstory text content from Lua to Python text lookup system. Lua stores only backstory IDs, Python resolves IDs to text via native dict constants.

## Technical Approach

### ID Format

**Unique Characters:**
```
unique.{technical_name}
```
Examples: `unique.wolf`, `unique.esc_m_trader`, `unique.bar_visitors_barman_stalker_trader`

**Faction Characters:**
```
{faction}.{number}
```
Examples: `loner.1`, `bandit.3`, `duty.2`

**Generic Fallback:**
```
generic.{number}
```
Example: `generic.1` (used when faction not found)

### Lua Side (.ltx)

**File:** `gamedata/configs/talker/backstories.ltx`

```ini
[unique]
ids = esc_m_trader, esc_2_12_stalker_wolf, bar_visitors_barman_stalker_trader, ...

[loner]
ids = 1, 2, 3, 4, 5

[bandit]
ids = 1, 2, 3

[duty]
ids = 1, 2, 3, 4

[freedom]
ids = 1, 2, 3

[generic]
ids = 1, 2, 3, 4, 5
```

**Loading Logic:**
```lua
local ini = ini_file("talker\\backstories.ltx")

function get_random_backstory_id(faction)
    local section = faction_to_section[string.lower(faction)] or "generic"
    if not ini:section_exist(section) then
        section = "generic"
    end
    
    local ids_str = ini:r_string_ex(section, "ids")
    local ids = parse_ids(ids_str)
    local idx = math.random(1, #ids)
    return section .. "." .. ids[idx]
end

function get_backstory_id(character)
    -- Check for unique character
    if queries.is_unique_character_by_id(character.game_id) then
        local tech_name = queries.get_technical_name_by_id(character.game_id)
        return "unique." .. string.lower(tech_name)
    end
    
    -- Generic character - get random backstory
    return get_random_backstory_id(character.faction)
end
```

### Python Side (Dict Modules)

**Folder Structure:**
```
talker_service/texts/
├── backstory/
│   ├── __init__.py
│   ├── unique.py
│   ├── loner.py
│   ├── bandit.py
│   ├── duty.py
│   ├── freedom.py
│   ├── generic.py
│   └── ...
└── personality/
    └── ...
```

**Module Format:**
```python
# texts/backstory/unique.py
TEXTS = {
    "esc_m_trader": "Sidorovich is a cunning information broker...",
    "esc_2_12_stalker_wolf": "Wolf maintains security at the rookie village...",
    "bar_visitors_barman_stalker_trader": "The Barkeep runs 100 Rads bar...",
}
```

```python
# texts/backstory/loner.py
TEXTS = {
    "1": "A former factory worker who came to the Zone seeking fortune...",
    "2": "An ex-military scout who deserted after witnessing horrors...",
    "3": "A scientist's assistant who got stranded during an expedition...",
}
```

**Resolution Logic:**
```python
from importlib import import_module
from typing import Dict

_backstory_modules: Dict[str, Dict[str, str]] = {}

def _get_backstory_module(faction: str) -> Dict[str, str]:
    if faction not in _backstory_modules:
        try:
            module = import_module(f"texts.backstory.{faction}")
            _backstory_modules[faction] = getattr(module, 'TEXTS', {})
        except ImportError:
            _backstory_modules[faction] = {}
    return _backstory_modules[faction]

def resolve_backstory(backstory_id: str) -> str:
    """Resolve backstory ID to text.
    
    Args:
        backstory_id: e.g., "unique.wolf", "loner.3"
    
    Returns:
        Text or empty string if not found
    """
    if not backstory_id or "." not in backstory_id:
        return ""
    
    faction, key = backstory_id.split(".", 1)
    texts = _get_backstory_module(faction)
    return texts.get(key, "")
```

### Character Model Changes

**Before:**
```lua
character = {
    game_id = 123,
    name = "Wolf",
    backstory = "Wolf is a veteran stalker who has survived...",  -- Full text
}
```

**After:**
```lua
character = {
    game_id = 123,
    name = "Wolf",
    backstory_id = "unique.esc_2_12_stalker_wolf",  -- Just ID
}
```

## Files to Modify

### Lua
| File | Change |
|------|--------|
| `gamedata/configs/talker/backstories.ltx` | NEW - Create with ID lists |
| `bin/lua/domain/repo/backstories.lua` | Load IDs from .ltx, return ID strings |
| `bin/lua/domain/model/character.lua` | Add backstory_id field |

### Python
| File | Change |
|------|--------|
| `talker_service/texts/backstory/*.py` | NEW - Create text modules |
| `talker_service/src/talker_service/prompts/lookup.py` | Add resolve_backstory() function |
| `talker_service/src/talker_service/prompts/builder.py` | Use resolve_backstory() |

## Testing Strategy

### Lua Tests
1. Test loading IDs from .ltx file
2. Test unique character backstory ID assignment
3. Test generic character backstory ID assignment
4. Test fallback to generic for unknown faction

### Python Tests
1. Test resolve_backstory() with valid unique ID
2. Test resolve_backstory() with valid faction ID
3. Test resolve_backstory() with invalid ID
4. Test resolve_backstory() returns empty for unknown module
5. Test integration with prompt builder
