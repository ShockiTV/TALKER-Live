# Personalities Text Lookup Migration

## Purpose

Move personality text content from Lua XML files to Python text lookup system. Lua stores only personality IDs (e.g., "bandit.3"), Python resolves IDs to text via native dict constants. This reduces Lua memory footprint and centralizes text content in Python.

## Requirements

### REQ-1: Create .ltx file with personality ID lists

Lua reads valid personality IDs from a .ltx config file, not XML.

#### Scenario: Load personality IDs from .ltx

- GIVEN gamedata/configs/talker/personalities.ltx exists with format:
  ```
  [bandit]
  ids = 1, 2, 3, 4, 5
  
  [loner]
  ids = 1, 2, 3, 4, 5, 6
  ```
- WHEN personalities module initializes
- THEN it can read available IDs for each faction

### REQ-2: Assign personality IDs instead of text

When assigning a personality to a character, store only the ID string.

#### Scenario: Assign random personality ID

- GIVEN a character with faction "Bandit"
- WHEN get_personality(character) is called for the first time
- THEN character receives a personality_id like "bandit.3"
- AND the ID is stored in character_personalities cache

### REQ-3: Python texts folder structure

Python has text modules organized by category, storing dict constants.

#### Scenario: Text module structure

- GIVEN texts folder exists at talker_service/texts/
- THEN structure is:
  ```
  texts/
    personality/
      bandit.py    # TEXTS = {"1": "morose", "2": "sarcastic", ...}
      generic.py
      unique.py
      ...
    backstory/
      bandit.py
      ...
  ```

### REQ-4: Python resolves personality IDs to text

Python prompts module resolves personality IDs to text via lookup.

#### Scenario: Resolve personality ID

- GIVEN personality_id = "bandit.3"
- WHEN resolve_personality(personality_id) is called
- THEN returns the text from texts/personality/bandit.py TEXTS["3"]

### REQ-5: Fallback to generic

If personality not found in faction module, fall back to generic.

#### Scenario: Fallback to generic

- GIVEN personality_id = "bandit.999"
- AND texts/personality/bandit.py TEXTS does not have key "999"
- WHEN resolve_personality(personality_id) is called
- THEN returns empty string (ID not found)

### REQ-6: Character stores personality_id field

Character model uses personality_id instead of personality for ID-based storage.

#### Scenario: Character with personality ID

- GIVEN a character is created with personality_id = "loner.5"
- WHEN character is serialized for event_store
- THEN saved data contains personality_id field (not personality)
- AND personality_id value is "loner.5"

### REQ-7: Remove XML trait files

Delete the old XML trait files after migration.

#### Scenario: XML files removed

- WHEN migration is complete
- THEN gamedata/configs/text/eng/talker_traits_*.xml files are deleted
- AND personalities.lua no longer calls queries.load_random_xml()

## Tasks

### Lua Tasks
- [x] Create gamedata/configs/talker/personalities.ltx with ID lists per faction
- [x] Update personalities.lua to load IDs from .ltx instead of XML
- [x] Update personalities.lua to return IDs like "faction.N" instead of text
- [x] Update Character model to use personality_id field
- [x] Update game_adapter.create_character() to set personality_id
- [x] Delete talker_traits_*.xml files
- [x] Update tests for new ID-based system

### Python Tasks
- [x] ~~Add python-i18n to dependencies~~ (uses native Python dicts)
- [x] Create texts/personality/*.py modules (extract from XML)
- [x] Create prompts/lookup.py with resolve_personality() function
- [x] Update prompt helpers to resolve personality_id before using in prompts
- [x] Add tests for text lookup
