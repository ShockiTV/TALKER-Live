# Backstories Text Lookup Migration

## Purpose

Move backstory text content from Lua to Python text lookup system. Lua stores only backstory IDs (e.g., "unique.wolf" or "loner.2"), Python resolves IDs to text via native dict constants. This follows the same pattern as personalities migration.

## Requirements

### REQ-1: Create .ltx file with backstory ID lists

Lua reads valid backstory IDs from a .ltx config file.

#### Scenario: Load backstory IDs from .ltx

- GIVEN gamedata/configs/talker/backstories.ltx exists with format:
  ```
  [unique]
  ids = wolf, sidorovich, barkeep, sultan, lukash
  
  [loner]
  ids = 1, 2, 3, 4, 5
  
  [bandit]
  ids = 1, 2, 3
  ```
- WHEN backstories module initializes
- THEN it can read available IDs for unique characters and per-faction

### REQ-2: Assign backstory IDs instead of text

When assigning a backstory to a character, store only the ID string.

#### Scenario: Assign unique backstory ID

- GIVEN a unique character "Wolf"
- WHEN get_backstory(character) is called
- THEN character receives backstory_id "unique.wolf"

#### Scenario: Assign generic backstory ID

- GIVEN a non-unique character with faction "Loner"
- WHEN get_backstory(character) is called
- THEN character receives backstory_id like "loner.2"

### REQ-3: Python texts folder structure for backstories

Python has text modules organized by category, storing dict constants.

#### Scenario: Text module structure

- GIVEN texts folder exists at talker_service/texts/
- THEN backstory structure is:
  ```
  texts/
    backstory/
      unique.py     # TEXTS = {"wolf": "Wolf is a veteran...", ...}
      loner.py      # TEXTS = {"1": "A former factory worker...", ...}
      bandit.py
      generic.py
      ...
  ```

### REQ-4: Python resolves backstory IDs to text

Python prompts module resolves backstory IDs to text via lookup.

#### Scenario: Resolve unique backstory ID

- GIVEN backstory_id = "unique.wolf"
- WHEN resolve_backstory(backstory_id) is called
- THEN returns the text from texts/backstory/unique.py TEXTS["wolf"]

#### Scenario: Resolve faction backstory ID

- GIVEN backstory_id = "loner.2"
- WHEN resolve_backstory(backstory_id) is called
- THEN returns the text from texts/backstory/loner.py TEXTS["2"]

### REQ-5: Fallback to empty string

If backstory not found in module, return empty string.

#### Scenario: Fallback for missing backstory

- GIVEN backstory_id = "unknown.99"
- AND texts/backstory/unknown.py does not exist
- WHEN resolve_backstory(backstory_id) is called
- THEN returns empty string

### REQ-6: Character stores backstory_id field

Character model uses backstory_id instead of backstory for ID-based storage.

#### Scenario: Character with backstory ID

- GIVEN a character is created with backstory_id = "unique.wolf"
- WHEN character is serialized for event_store
- THEN saved data contains backstory_id field (not backstory)
- AND backstory_id value is "unique.wolf"

### REQ-7: Remove XML backstory files

Delete the old XML backstory files after migration (if any).

#### Scenario: XML files removed

- WHEN migration is complete
- THEN backstories.lua no longer calls queries.load_xml()
- AND loads from .ltx only

## Tasks

### Lua Tasks
- [x] Create gamedata/configs/talker/backstories.ltx with ID lists
- [x] Update backstories.lua to load IDs from .ltx
- [x] Update backstories.lua to return IDs like "faction.N" or "unique.name"
- [x] Update Character model to use backstory_id field
- [x] Update tests for new ID-based system

### Python Tasks
- [x] Create texts/backstory/*.py modules (extract from Lua)
- [x] Create prompts/lookup.py with resolve_backstory() function
- [x] Update prompt builder to resolve backstory_id before using in prompts
- [x] Add tests for text lookup
