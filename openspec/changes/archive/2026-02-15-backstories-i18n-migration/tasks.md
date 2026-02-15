# Backstories Text Lookup Migration - Tasks

## 1. Python Setup

- [x] 1.1 Create texts/backstory/ folder structure
- [x] 1.2 Create prompts/lookup.py module with resolve_backstory() function
- [x] 1.3 Configure module imports and caching

## 2. Extract Backstory Content to Python Modules

- [x] 2.1 Extract unique character backstories → unique.py
- [x] 2.2 Extract generic backstories → generic.py
- [x] 2.3 Extract bandit backstories → bandit.py
- [x] 2.4 Extract duty backstories → duty.py
- [x] 2.5 Extract freedom backstories → freedom.py
- [x] 2.6 Extract army backstories → army.py
- [x] 2.7 Extract ecolog backstories → ecolog.py
- [x] 2.8 Extract mercenary backstories → mercenary.py
- [x] 2.9 Extract monolith backstories → monolith.py
- [x] 2.10 Extract renegade backstories → renegade.py
- [x] 2.11 Extract sin backstories → sin.py
- [x] 2.12 Extract clearsky backstories → clearsky.py
- [x] 2.13 Extract isg backstories → isg.py
- [x] 2.14 Verify all Python modules are valid and complete

## 3. Lua .ltx Configuration

- [x] 3.1 Create gamedata/configs/talker/backstories.ltx
- [x] 3.2 Add [unique] section with unique character IDs
- [x] 3.3 Add faction sections (loner, bandit, duty, etc.) with backstory IDs
- [x] 3.4 Add [generic] fallback section

## 4. Lua Code Changes

- [x] 4.1 Update backstories.lua to load from .ltx
- [x] 4.2 Update backstories.lua get_backstory() to return ID string
- [x] 4.3 Add faction_to_section mapping table
- [x] 4.4 Handle unique characters with "unique.{tech_name}" ID format
- [x] 4.5 Handle generic fallback for unknown factions

## 5. Python Integration

- [x] 5.1 Update prompt builder to call resolve_backstory()
- [x] 5.2 Handle both old (full text) and new (ID) backstory fields

## 6. Testing

- [x] 6.1 Add Python tests for resolve_backstory() with unique ID
- [x] 6.2 Add Python tests for resolve_backstory() with faction ID
- [x] 6.3 Add Python tests for resolve_backstory() with invalid ID
- [x] 6.4 Add Lua tests for backstories.lua .ltx loading
- [x] 6.5 Add Lua tests for get_backstory_id() function
- [x] 6.6 Manual test: verify backstory shows in dialogue prompt

## 7. Cleanup

- [x] 7.1 Remove old backstory text data from Lua files (if any)
- [x] 7.2 Update documentation (AGENTS.md, copilot-instructions.md)
