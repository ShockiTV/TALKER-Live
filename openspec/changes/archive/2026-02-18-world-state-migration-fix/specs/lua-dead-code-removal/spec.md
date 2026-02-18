# lua-dead-code-removal

## Purpose

Remove Lua functions that have been migrated to Python and are no longer used in TALKER-Expanded.

## REMOVED Requirements

### Requirement: Event.describe functions

**Reason:** Event-to-text rendering is now handled by Python prompt builders. These functions have no production callers in TALKER-Expanded.

**Migration:** Python `prompts/models.py` handles event description rendering.

Functions to remove from `bin/lua/domain/model/event.lua`:
- `Event.describe(event)`
- `Event.describe_short(event)` 
- `Event.describe_event(event)`
- `TEMPLATES` table (typed event templates)
- `describe_object(obj)` helper
- `table_to_args(table_input)` helper

#### Scenario: Event module no longer provides text rendering
- **WHEN** code attempts to call Event.describe()
- **THEN** function does not exist
- **AND** Python handles event rendering instead

### Requirement: Mention scanning functions

**Reason:** Faction/character/player mention scanning is now handled by Python. These functions exist in `game_adapter.lua` but have no callers in TALKER-Expanded.

**Migration:** Python world context builder handles mention filtering.

Functions to remove from `bin/lua/infra/game_adapter.lua`:
- `get_mentioned_factions(events)`
- `is_player_involved(events, player_name)`
- `get_mentioned_characters(events, current_location, notable_characters)`

#### Scenario: game_adapter no longer provides mention scanning
- **WHEN** code attempts to call game_adapter.get_mentioned_factions()
- **THEN** function does not exist
- **AND** Python handles mention scanning instead

### Requirement: Tests for removed functions

**Reason:** Tests for deleted functions must be removed or updated.

**Migration:** Remove corresponding test cases from `tests/entities/test_event.lua`.

#### Scenario: Event tests updated
- **WHEN** test suite runs
- **THEN** tests for Event.describe() are removed
- **AND** remaining tests pass

