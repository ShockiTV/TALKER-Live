# map-transition-save

## Purpose

Save/load behavior for map transition state. Persistence is handled by the `levels` domain repo via `talker_game_persistence.script`.

## Requirements

### Requirement: Map transition save persists visit counts
The map transition visit counts SHALL be persisted through the `levels` domain repo, not through local save/load callbacks in the trigger script.

#### Scenario: Save and reload preserves visit count
- **WHEN** the player has visited Garbage 3 times, saves, and reloads
- **THEN** the next transition to Garbage shows visit_count = 4

### Requirement: Trigger script delegates persistence
The map transition trigger script SHALL NOT have its own `save_state`/`load_state` callbacks. All persistence SHALL be handled by the `levels` domain repo through `talker_game_persistence.script`.

#### Scenario: No save/load callbacks in trigger
- **WHEN** inspecting `talker_trigger_map_transition.script`
- **THEN** there are no `save_state` or `load_state` function definitions
- **AND** there are no `RegisterScriptCallback` calls for save_state or load_state
