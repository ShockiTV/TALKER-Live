# lua-dead-code-removal

## Purpose

Documents Lua functions that have been migrated to Python and removed from TALKER-Expanded.

## Requirements

### Requirement: Event Text Rendering Removed

Event-to-text rendering is handled by Python prompt builders. The following functions have been removed from `bin/lua/domain/model/event.lua`:

- `Event.describe(event)`
- `Event.describe_short(event)` 
- `Event.describe_event(event)`
- `TEMPLATES` table (typed event templates)
- `describe_object(obj)` helper
- `table_to_args(table_input)` helper

**Migration:** Python `prompts/helpers.py` handles event description rendering.

#### Scenario: Event module no longer provides text rendering
- **WHEN** code attempts to call Event.describe()
- **THEN** function does not exist
- **AND** Python handles event rendering instead

### Requirement: Mention Scanning Removed

Faction/character/player mention scanning is handled by Python. The following functions have been removed from `bin/lua/infra/game_adapter.lua`:

- `get_mentioned_factions(events)`
- `is_player_involved(events, player_name)`
- `get_mentioned_characters(events, current_location, notable_characters)`

**Migration:** Python world context builder handles mention filtering.

#### Scenario: game_adapter no longer provides mention scanning
- **WHEN** code attempts to call game_adapter.get_mentioned_factions()
- **THEN** function does not exist
- **AND** Python handles mention scanning instead

### Requirement: Tests Updated

Tests for removed functions have been removed from `tests/entities/test_event.lua`.

#### Scenario: Event tests updated
- **WHEN** test suite runs
- **THEN** tests for Event.describe() are removed
- **AND** remaining tests pass
