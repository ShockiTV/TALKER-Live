# Personalities Text Lookup Migration - Design

## Overview

Move personality text content from Lua XML files to Python text lookup system. Lua stores only personality IDs, Python resolves IDs to text via native dict constants.

## Technical Approach

### ID Format

```
{faction}.{number}
```

Examples:
- `bandit.3` → "morose"
- `loner.7` → "pragmatic"
- `duty.2` → "disciplined"

### Lua Side (.ltx)

**File:** `gamedata/configs/talker/personalities.ltx`

```ini
[bandit]
ids = 1, 2, 3, 4, 5, 7, 9, 12

[loner]
ids = 1, 2, 3, 4, 5, 6, 7, 8

[duty]
ids = 1, 2, 3, 5, 6

[freedom]
ids = 1, 2, 3, 4, 5

; ... other factions
```

**Loading Logic:**
```lua
local ini = ini_file("talker\\personalities.ltx")

function get_random_personality_id(faction)
    local section = string.lower(faction)
    if not ini:section_exist(section) then
        section = "loner"  -- fallback
    end
    
    local ids_str = ini:r_string_ex(section, "ids") or "1"
    local ids = parse_comma_separated(ids_str)
    local idx = math.random(1, #ids)
    return section .. "." .. ids[idx]
end
```

### Python Side (Dict Modules)

**Folder Structure:**
```
talker_service/texts/
├── personality/
│   ├── __init__.py
│   ├── bandit.py
│   ├── generic.py
│   ├── unique.py
│   └── ...
└── backstory/
    ├── __init__.py
    └── ...
```

**Module Format:**
```python
# texts/personality/bandit.py
TEXTS = {
    "1": "morose",
    "2": "sarcastic",
    "3": "cautious",
    "5": "bloodthirsty",
    "7": "gritty",
}
```

**Resolution Logic:**
```python
from importlib import import_module
from typing import Dict

_personality_modules: Dict[str, Dict[str, str]] = {}

def _get_personality_module(faction: str) -> Dict[str, str]:
    if faction not in _personality_modules:
        try:
            module = import_module(f"texts.personality.{faction}")
            _personality_modules[faction] = getattr(module, 'TEXTS', {})
        except ImportError:
            _personality_modules[faction] = {}
    return _personality_modules[faction]

def resolve_personality(personality_id: str) -> str:
    """Resolve personality ID to text.
    
    Args:
        personality_id: e.g., "bandit.3"
    
    Returns:
        Text or empty string if not found
    """
    if not personality_id or "." not in personality_id:
        return ""
    
    faction, key = personality_id.split(".", 1)
    texts = _get_personality_module(faction)
    return texts.get(key, "")
```
```

### Character Model Changes

**Before:**
```lua
character = {
    game_id = 123,
    name = "Vasya",
    faction = "Bandit",
    personality = "morose and sarcastic",  -- Full text
}
```

**After:**
```lua
character = {
    game_id = 123,
    name = "Vasya",
    faction = "Bandit",
    personality_id = "bandit.3",  -- Just ID
}
```

### Unique Characters

Unique characters (Wolf, Sidorovich, etc.) use a separate lookup:
- ID format: `unique.{technical_name}`
- Example: `unique.wolf`, `unique.sidorovich`
- Stored in `texts/personality/unique.py`

## Files to Modify

### Lua
| File | Change |
|------|--------|
| `gamedata/configs/talker/personalities.ltx` | NEW - Create with ID lists |
| `bin/lua/domain/repo/personalities.lua` | Load IDs from .ltx, return ID strings |
| `bin/lua/domain/model/character.lua` | Add personality_id field |
| `bin/lua/infra/game_adapter.lua` | Set personality_id on character creation |
| `gamedata/configs/text/eng/talker_traits_*.xml` | DELETE after migration |

### Python
| File | Change |
|------|--------|
| `talker_service/texts/personality/*.py` | NEW - Create from XML content |
| `talker_service/src/talker_service/prompts/lookup.py` | NEW - Resolution functions |
| `talker_service/src/talker_service/prompts/helpers.py` | Use resolve_personality() |
| `pyproject.toml` | No additional dependencies needed (uses native dicts) |

## Data Migration

### Extract from XML to Python Modules

Script to convert existing XML:
```python
import xml.etree.ElementTree as ET
import re

def convert_traits_xml(xml_path, faction):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    result = {}
    for string in root.findall('string'):
        id_attr = string.get('id')
        text = string.find('text').text
        
        # Extract number from id like "talker_traits_Bandit_3"
        match = re.search(r'_(\d+)$', id_attr)
        if match:
            num = match.group(1)
            result[num] = text
    
    return result

def write_py_module(data, faction, output_path):
    lines = [f'"""{faction.title()} texts."""', '', 'TEXTS = {']
    for key, value in data.items():
        lines.append(f'    {repr(key)}: {repr(value)},')
    lines.append('}')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\\n'.join(lines) + '\\n')
```

## Testing Strategy

### Lua Tests
1. Test loading IDs from .ltx file
2. Test random ID selection per faction
3. Test fallback to loner for unknown faction
4. Test unique character ID assignment

### Python Tests
1. Test resolve_personality() with valid ID
2. Test resolve_personality() with invalid ID
3. Test resolve_personality() returns empty for unknown faction
4. Test integration with prompt helpers
