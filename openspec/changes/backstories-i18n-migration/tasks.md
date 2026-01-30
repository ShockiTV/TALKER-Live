# Backstories i18n Migration - Tasks

## Group 1: Python i18n Setup
*Depends on: personalities-i18n-migration Group 1 (shared setup)*

- [ ] Task 1.1: Add backstory namespace to i18n initialization in `prompts/__init__.py` (if not already done)
- [ ] Task 1.2: Create placeholder `translations/en/backstory/.gitkeep`

## Group 2: Extract Current Backstory Content

- [ ] Task 2.1: Read `bin/lua/domain/repo/backstories.lua` to catalog existing unique character backstories
- [ ] Task 2.2: Identify unique characters from `bin/lua/infra/STALKER/unique_characters.lua`
- [ ] Task 2.3: Document existing backstory content → backstory ID mapping
- [ ] Task 2.4: Create `translations/en/backstory/unique.json` with unique character backstories
- [ ] Task 2.5: Create `translations/en/backstory/generic_loner.json` with generic loner backstories
- [ ] Task 2.6: Create `translations/en/backstory/generic_bandit.json` with generic bandit backstories
- [ ] Task 2.7: Create `translations/en/backstory/generic_duty.json` with generic Duty backstories
- [ ] Task 2.8: Create `translations/en/backstory/generic_freedom.json` with generic Freedom backstories
- [ ] Task 2.9: Create `translations/en/backstory/generic_army.json` with generic Military backstories
- [ ] Task 2.10: Create `translations/en/backstory/generic_ecologist.json` with generic Ecologist backstories
- [ ] Task 2.11: Create remaining faction backstory JSON files

## Group 3: Create Lua .ltx Configuration

- [ ] Task 3.1: Create `gamedata/configs/talker/backstories.ltx` with [unique] section listing all unique character names
- [ ] Task 3.2: Add [generic_loner] section with available backstory IDs
- [ ] Task 3.3: Add [generic_bandit] section with available backstory IDs
- [ ] Task 3.4: Add remaining faction sections to .ltx

## Group 4: Modify Lua Code

- [ ] Task 4.1: Update `bin/lua/domain/repo/backstories.lua` to load .ltx file
- [ ] Task 4.2: Add `get_backstory_id(character)` function that returns ID string
- [ ] Task 4.3: Update `bin/lua/domain/model/character.lua` - add `backstory_id` field
- [ ] Task 4.4: Update `bin/lua/infra/game_adapter.lua` - set backstory_id when creating character
- [ ] Task 4.5: Update ZMQ serialization in `bin/lua/infra/zmq/publisher.lua` to send backstory_id
- [ ] Task 4.6: Remove backstory text loading from Lua (keep only ID assignment)

## Group 5: Python Integration

- [ ] Task 5.1: Create `resolve_backstory(backstory_id, locale)` function in `prompts/i18n.py`
- [ ] Task 5.2: Update `prompts/helpers.py` to resolve backstory_id to text
- [ ] Task 5.3: Update Character model in `prompts/models.py` to accept backstory_id
- [ ] Task 5.4: Update `state/models.py` Character if needed
- [ ] Task 5.5: Update dialogue prompt builder to use resolved backstory

## Group 6: Testing

- [ ] Task 6.1: Create test for .ltx loading in Lua
- [ ] Task 6.2: Create test for `get_backstory_id()` with unique characters
- [ ] Task 6.3: Create test for `get_backstory_id()` with generic characters
- [ ] Task 6.4: Create test for `get_backstory_id()` fallback to generic_loner
- [ ] Task 6.5: Create Python test for `resolve_backstory()` with unique ID
- [ ] Task 6.6: Create Python test for `resolve_backstory()` with generic ID
- [ ] Task 6.7: Create Python test for `resolve_backstory()` with invalid ID
- [ ] Task 6.8: Create Python test for locale fallback

## Group 7: Cleanup & Validation

- [ ] Task 7.1: Remove old backstory text data from Lua files
- [ ] Task 7.2: Update documentation with backstory ID format
- [ ] Task 7.3: Run full Lua test suite
- [ ] Task 7.4: Run full Python test suite
- [ ] Task 7.5: Integration test: verify backstory appears in generated dialogue

## Dependencies

- **REQUIRES** event-store-versioning to be completed first
- **SHOULD** follow personalities-i18n-migration (shared patterns and i18n setup)
