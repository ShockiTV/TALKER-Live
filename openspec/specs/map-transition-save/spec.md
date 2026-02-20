# map-transition-save

## Purpose

Save/load behavior for map transition state in `talker_trigger_map_transition.script`.

## Requirements

### Requirement: Map transition save persists visit counts
The map transition save/load SHALL correctly persist `level_visit_count` across game saves.

#### Scenario: Save and reload preserves visit count
- **WHEN** the player has visited Garbage 3 times, saves, and reloads
- **THEN** the next transition to Garbage shows visit_count = 4

### Requirement: No dead code in save/load
The map transition save/load SHALL NOT persist unused variables.

#### Scenario: commented_already is removed
- **WHEN** inspecting the save_state and load_state functions
- **THEN** there is no reference to `commented_already`
