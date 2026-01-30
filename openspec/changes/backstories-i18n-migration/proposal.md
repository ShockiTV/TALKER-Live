# Backstories i18n Migration

## Purpose

Move backstory text content from Lua XML files to Python i18n system. Lua stores only backstory IDs (e.g., "unique.wolf" or "generic.loner.2"), Python resolves IDs to localized text. This follows the same pattern as personalities migration.

## Requirements

### REQ-1: Create .ltx file with backstory ID lists

Lua reads valid backstory IDs from a .ltx config file.

#### Scenario: Load backstory IDs from .ltx

- GIVEN gamedata/configs/talker/backstories.ltx exists with format:
  ```
  [unique]
  ids = wolf, sidorovich, barkeep, sultan, lukash
  
  [generic_loner]
  ids = 1, 2, 3, 4, 5
  
  [generic_bandit]
  ids = 1, 2, 3
  ```
- WHEN backstories module initializes
- THEN it can read available IDs for unique characters and generic per-faction

### REQ-2: Assign backstory IDs instead of text

When assigning a backstory to a character, store only the ID string.

#### Scenario: Assign unique backstory ID

- GIVEN a unique character "Wolf"
- WHEN get_backstory(character) is called
- THEN character receives backstory_id "unique.wolf"

#### Scenario: Assign generic backstory ID

- GIVEN a non-unique character with faction "Loner"
- WHEN get_backstory(character) is called
- THEN character receives backstory_id like "generic.loner.2"

### REQ-3: Python i18n folder structure for backstories

Python has JSON translation files for backstories.

#### Scenario: Backstory translation file structure

- GIVEN translations folder exists at talker_service/translations/
- THEN backstory structure is:
  ```
  translations/
    en/
      backstory/
        unique.json       # {"wolf": "Wolf is a veteran...", "sidorovich": "..."}
        generic_loner.json
        generic_bandit.json
        ...
    ru/
      backstory/
        unique.json
        ...
  ```

### REQ-4: Python resolves backstory IDs to text

Python prompts module resolves backstory IDs to localized text.

#### Scenario: Resolve unique backstory ID

- GIVEN backstory_id = "unique.wolf"
- AND locale = "en"
- WHEN resolve_backstory(backstory_id) is called
- THEN returns the text from en/backstory/unique.json key "wolf"

#### Scenario: Resolve generic backstory ID

- GIVEN backstory_id = "generic.loner.2"
- AND locale = "en"
- WHEN resolve_backstory(backstory_id) is called
- THEN returns the text from en/backstory/generic_loner.json key "2"

### REQ-5: Fallback to English for backstories

If translation missing in current locale, fall back to English.

#### Scenario: Backstory fallback to English

- GIVEN backstory_id = "unique.wolf"
- AND locale = "ru"
- AND ru/backstory/unique.json does not have key "wolf"
- WHEN resolve_backstory(backstory_id) is called
- THEN returns the text from en/backstory/unique.json key "wolf"

### REQ-6: Character stores backstory_id field

Character model uses backstory_id instead of backstory for ID-based storage.

#### Scenario: Character with backstory ID

- GIVEN a character is created with backstory_id = "unique.wolf"
- WHEN character is serialized for event_store
- THEN saved data contains backstory_id field (not backstory)
- AND backstory_id value is "unique.wolf"

### REQ-7: Remove XML backstory files

Delete the old XML backstory files after migration.

#### Scenario: XML files removed

- WHEN migration is complete
- THEN gamedata/configs/text/eng/talker_backstory*.xml files are deleted (if any)
- AND backstories.lua no longer calls queries.load_xml()

## Tasks

### Lua Tasks
- [ ] Create gamedata/configs/talker/backstories.ltx with ID lists
- [ ] Update backstories.lua to load IDs from .ltx instead of XML
- [ ] Update backstories.lua to return IDs like "unique.name" or "generic.faction.N"
- [ ] Update Character model to use backstory_id field
- [ ] Update game_adapter.create_character() to set backstory_id
- [ ] Delete backstory XML files (if separate from traits)
- [ ] Update tests for new ID-based system

### Python Tasks
- [ ] Create translations/en/backstory/*.json files (extract from XML/Lua)
- [ ] Add resolve_backstory() function to prompts/i18n.py
- [ ] Update prompt helpers to resolve backstory_id before using in prompts
- [ ] Add tests for backstory i18n resolution
