# Personalities Text Lookup Migration - Tasks

## 1. Python Setup

- [x] 1.1 ~~Add python-i18n to pyproject.toml dependencies~~ (uses native Python dicts)
- [x] 1.2 Create texts/ folder structure
- [x] 1.3 Create prompts/lookup.py module with resolve_personality() function
- [x] 1.4 Configure module imports and caching

## 2. Extract XML Content to Python Modules

- [x] 2.1 Write extraction script to convert XML to Python modules
- [x] 2.2 Extract talker_traits.xml (generic traits) → generic.py
- [x] 2.3 Extract talker_traits_Bandit.xml → bandit.py
- [x] 2.4 Extract talker_traits_Renegade.xml → renegade.py
- [x] 2.5 Extract talker_traits_Monolith.xml → monolith.py
- [x] 2.6 Extract talker_traits_Ecolog.xml → ecolog.py
- [x] 2.7 Extract talker_traits_Sin.xml → sin.py
- [x] 2.8 Extract talker_traits_Zombied.xml → zombied.py
- [x] 2.9 Extract talker_traits_unique.xml → unique.py
- [x] 2.10 Verify all Python modules are valid and complete

## 3. Lua .ltx Configuration

- [x] 3.1 Create gamedata/configs/talker/personalities.ltx
- [x] 3.2 Add ID lists for each faction based on extracted module keys
- [x] 3.3 Add fallback section for generic traits

## 4. Lua Code Changes

- [x] 4.1 Update personalities.lua to load from .ltx instead of XML
- [x] 4.2 Update personalities.lua get_personality() to return ID string
- [x] 4.3 Update Character model to use personality_id field
- [x] 4.4 Update game_adapter.create_character() to set personality_id
- [x] 4.5 Handle unique characters with "unique.{name}" ID format

## 5. Python Integration

- [x] 5.1 Update prompt helpers to call resolve_personality()
- [x] 5.2 Handle both old (full text) and new (ID) personality fields
- [x] 5.3 Add locale configuration from MCM settings (using default "en" for now)

## 6. Testing

- [x] 6.1 Add Python tests for resolve_personality()
- [x] 6.2 Add Python tests for locale fallback
- [x] 6.3 Update Lua tests for personalities.lua
- [x] 6.4 Manual test: verify personality shows in dialogue prompt

## 7. Cleanup

- [x] 7.1 Delete gamedata/configs/text/eng/talker_traits_*.xml files
- [x] 7.2 Remove XML loading code from personalities.lua (no XML code remained, .ltx only)
- [x] 7.3 Update documentation (AGENTS.md, copilot-instructions.md)
