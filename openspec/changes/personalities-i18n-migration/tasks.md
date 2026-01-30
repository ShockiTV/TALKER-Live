# Personalities i18n Migration - Tasks

## 1. Python Setup

- [ ] 1.1 Add python-i18n to pyproject.toml dependencies
- [ ] 1.2 Create translations/ folder structure
- [ ] 1.3 Create prompts/i18n.py module with resolve_personality() function
- [ ] 1.4 Configure i18n load path and fallback locale

## 2. Extract XML Content to JSON

- [ ] 2.1 Write extraction script to convert XML to JSON
- [ ] 2.2 Extract talker_traits.xml (generic traits) → generic.json
- [ ] 2.3 Extract talker_traits_Bandit.xml → bandit.json
- [ ] 2.4 Extract talker_traits_Renegade.xml → renegade.json
- [ ] 2.5 Extract talker_traits_Monolith.xml → monolith.json
- [ ] 2.6 Extract talker_traits_Ecolog.xml → ecolog.json
- [ ] 2.7 Extract talker_traits_Sin.xml → sin.json
- [ ] 2.8 Extract talker_traits_Zombied.xml → zombied.json
- [ ] 2.9 Extract talker_traits_unique.xml → unique.json
- [ ] 2.10 Verify all JSON files are valid and complete

## 3. Lua .ltx Configuration

- [ ] 3.1 Create gamedata/configs/talker/personalities.ltx
- [ ] 3.2 Add ID lists for each faction based on extracted JSON keys
- [ ] 3.3 Add fallback section for generic traits

## 4. Lua Code Changes

- [ ] 4.1 Update personalities.lua to load from .ltx instead of XML
- [ ] 4.2 Update personalities.lua get_personality() to return ID string
- [ ] 4.3 Update Character model to use personality_id field
- [ ] 4.4 Update game_adapter.create_character() to set personality_id
- [ ] 4.5 Handle unique characters with "unique.{name}" ID format

## 5. Python Integration

- [ ] 5.1 Update prompt helpers to call resolve_personality()
- [ ] 5.2 Handle both old (full text) and new (ID) personality fields
- [ ] 5.3 Add locale configuration from MCM settings

## 6. Testing

- [ ] 6.1 Add Python tests for resolve_personality()
- [ ] 6.2 Add Python tests for locale fallback
- [ ] 6.3 Update Lua tests for personalities.lua
- [ ] 6.4 Manual test: verify personality shows in dialogue prompt

## 7. Cleanup

- [ ] 7.1 Delete gamedata/configs/text/eng/talker_traits_*.xml files
- [ ] 7.2 Remove XML loading code from personalities.lua
- [ ] 7.3 Update documentation
