# Personalities i18n Migration - Design

## Overview

Move personality text content from Lua XML files to Python i18n system. Lua stores only personality IDs, Python resolves IDs to localized text.

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

### Python Side (JSON)

**Folder Structure:**
```
talker_service/translations/
├── en/
│   └── personality/
│       ├── bandit.json
│       ├── loner.json
│       ├── duty.json
│       └── ...
└── ru/
    └── personality/
        └── ...
```

**JSON Format:**
```json
{
  "1": "morose",
  "2": "sarcastic",
  "3": "cautious",
  "5": "bloodthirsty",
  "7": "gritty"
}
```

**Resolution Logic:**
```python
import i18n

i18n.set('load_path', ['translations'])
i18n.set('fallback', 'en')

def resolve_personality(personality_id: str, locale: str = 'en') -> str:
    """Resolve personality ID to text.
    
    Args:
        personality_id: e.g., "bandit.3"
        locale: e.g., "en", "ru"
    
    Returns:
        Localized text or empty string if not found
    """
    if not personality_id:
        return ""
    
    parts = personality_id.split(".")
    if len(parts) != 2:
        return personality_id  # Return as-is if invalid format
    
    faction, num = parts
    i18n.set('locale', locale)
    return i18n.t(f"personality.{faction}.{num}", default="")
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
- Stored in `translations/en/personality/unique.json`

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
| `talker_service/translations/en/personality/*.json` | NEW - Create from XML content |
| `talker_service/src/talker_service/prompts/i18n.py` | NEW - Resolution functions |
| `talker_service/src/talker_service/prompts/helpers.py` | Use resolve_personality() |
| `pyproject.toml` | Add python-i18n dependency |

## Data Migration

### Extract from XML to JSON

Script to convert existing XML:
```python
import xml.etree.ElementTree as ET
import json
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
3. Test fallback to English locale
4. Test integration with prompt helpers
