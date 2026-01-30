# Backstories i18n Migration - Design

## Overview

Move backstory text content from Lua to Python i18n system, following the same pattern as personalities. Lua stores only backstory IDs, Python resolves IDs to localized text.

## Technical Approach

### ID Format

**Unique Characters:**
```
unique.{technical_name}
```
Examples: `unique.wolf`, `unique.sidorovich`, `unique.barkeep`

**Generic Characters:**
```
generic.{faction}.{number}
```
Examples: `generic.loner.1`, `generic.bandit.3`

### Lua Side (.ltx)

**File:** `gamedata/configs/talker/backstories.ltx`

```ini
[unique]
ids = wolf, sidorovich, barkeep, sultan, lukash, voronin, skinflint, owl, beard, hawaiian

[generic_loner]
ids = 1, 2, 3, 4, 5

[generic_bandit]
ids = 1, 2, 3

[generic_duty]
ids = 1, 2, 3, 4

; ... other factions
```

**Loading Logic:**
```lua
local ini = ini_file("talker\\backstories.ltx")

function get_backstory_id(character)
    -- Check if unique character
    local tech_name = queries.get_technical_name_by_id(character.game_id)
    if unique_characters[tech_name] then
        return "unique." .. string.lower(tech_name)
    end
    
    -- Generic character
    local faction = string.lower(character.faction)
    local section = "generic_" .. faction
    if not ini:section_exist(section) then
        section = "generic_loner"  -- fallback
    end
    
    local ids_str = ini:r_string_ex(section, "ids") or "1"
    local ids = parse_comma_separated(ids_str)
    local idx = math.random(1, #ids)
    return "generic." .. faction .. "." .. ids[idx]
end
```

### Python Side (JSON)

**Folder Structure:**
```
talker_service/translations/
├── en/
│   └── backstory/
│       ├── unique.json
│       ├── generic_loner.json
│       ├── generic_bandit.json
│       └── ...
└── ru/
    └── backstory/
        └── ...
```

**unique.json Format:**
```json
{
  "wolf": "Wolf is a veteran stalker who has survived countless anomalies...",
  "sidorovich": "Sidorovich is a cunning trader who has operated in the Zone since...",
  "barkeep": "The Barkeep runs the 100 Rads bar with an iron fist..."
}
```

**generic_loner.json Format:**
```json
{
  "1": "A former factory worker who came to the Zone seeking fortune...",
  "2": "An ex-military scout who deserted after witnessing the true horrors...",
  "3": "A scientist's assistant who got stranded during an expedition..."
}
```

**Resolution Logic:**
```python
def resolve_backstory(backstory_id: str, locale: str = 'en') -> str:
    """Resolve backstory ID to text.
    
    Args:
        backstory_id: e.g., "unique.wolf" or "generic.loner.3"
        locale: e.g., "en", "ru"
    
    Returns:
        Localized backstory text or empty string if not found
    """
    if not backstory_id:
        return ""
    
    parts = backstory_id.split(".")
    
    if parts[0] == "unique" and len(parts) == 2:
        # unique.wolf → backstory.unique.wolf
        name = parts[1]
        i18n.set('locale', locale)
        return i18n.t(f"backstory.unique.{name}", default="")
    
    elif parts[0] == "generic" and len(parts) == 3:
        # generic.loner.3 → backstory.generic_loner.3
        faction, num = parts[1], parts[2]
        i18n.set('locale', locale)
        return i18n.t(f"backstory.generic_{faction}.{num}", default="")
    
    return ""  # Invalid format
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
    backstory_id = "unique.wolf",  -- Just ID
}
```

## Files to Modify

### Lua
| File | Change |
|------|--------|
| `gamedata/configs/talker/backstories.ltx` | NEW - Create with ID lists |
| `bin/lua/domain/repo/backstories.lua` | Load IDs from .ltx, return ID strings |
| `bin/lua/domain/model/character.lua` | Add backstory_id field |
| `bin/lua/infra/game_adapter.lua` | Set backstory_id on character creation |
| `bin/lua/infra/STALKER/unique_characters.lua` | Reference for unique character detection |

### Python
| File | Change |
|------|--------|
| `talker_service/translations/en/backstory/*.json` | NEW - Create backstory content |
| `talker_service/src/talker_service/prompts/i18n.py` | Add resolve_backstory() function |
| `talker_service/src/talker_service/prompts/helpers.py` | Use resolve_backstory() |

## Backstory Content Source

Current backstories are defined in:
- `bin/lua/domain/repo/backstories.lua` - Has hardcoded backstory text for unique characters
- `bin/lua/infra/STALKER/unique_characters.lua` - Maps technical names to character info

Need to extract these to JSON files.

## Testing Strategy

### Lua Tests
1. Test unique character backstory ID assignment
2. Test generic character backstory ID assignment
3. Test fallback to generic_loner for unknown faction

### Python Tests
1. Test resolve_backstory() with unique ID
2. Test resolve_backstory() with generic ID
3. Test resolve_backstory() with invalid ID
4. Test fallback to English locale
