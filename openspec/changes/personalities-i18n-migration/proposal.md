# Personalities i18n Migration

## Purpose

Move personality text content from Lua XML files to Python i18n system. Lua stores only personality IDs (e.g., "bandit.3"), Python resolves IDs to localized text. This reduces Lua memory footprint and enables multi-language support.

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

### REQ-3: Python i18n folder structure

Python has JSON translation files organized by locale and category.

#### Scenario: Translation file structure

- GIVEN translations folder exists at talker_service/translations/
- THEN structure is:
  ```
  translations/
    en/
      personality/
        bandit.json    # {"1": "morose", "2": "sarcastic", ...}
        loner.json
        duty.json
        ...
    ru/
      personality/
        bandit.json
        ...
  ```

### REQ-4: Python resolves personality IDs to text

Python prompts module resolves personality IDs to localized text.

#### Scenario: Resolve personality ID

- GIVEN personality_id = "bandit.3"
- AND locale = "en"
- WHEN resolve_personality(personality_id) is called
- THEN returns the text from en/personality/bandit.json key "3"

### REQ-5: Fallback to English

If translation missing in current locale, fall back to English.

#### Scenario: Fallback to English

- GIVEN personality_id = "bandit.3"
- AND locale = "ru"
- AND ru/personality/bandit.json does not have key "3"
- WHEN resolve_personality(personality_id) is called
- THEN returns the text from en/personality/bandit.json key "3"

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
- [ ] Create gamedata/configs/talker/personalities.ltx with ID lists per faction
- [ ] Update personalities.lua to load IDs from .ltx instead of XML
- [ ] Update personalities.lua to return IDs like "faction.N" instead of text
- [ ] Update Character model to use personality_id field
- [ ] Update game_adapter.create_character() to set personality_id
- [ ] Delete talker_traits_*.xml files
- [ ] Update tests for new ID-based system

### Python Tasks
- [ ] Add python-i18n to dependencies
- [ ] Create translations/en/personality/*.json files (extract from XML)
- [ ] Create prompts/i18n.py with resolve_personality() function
- [ ] Update prompt helpers to resolve personality_id before using in prompts
- [ ] Add locale configuration (default: en)
- [ ] Add tests for i18n resolution and fallback
