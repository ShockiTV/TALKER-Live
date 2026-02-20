# levels-store

## Purpose

Domain repository for tracking level visits, including visit counts, detailed visit logs with timestamps/companions, and transition detection state (`from_level`).

## Requirements

### Requirement: Record a visit

The levels store SHALL record a visit when a level transition occurs.

#### Scenario: First visit to a level
- **WHEN** `record_visit(level_id, game_time_ms, from_level, companions)` is called for a level with no prior visits
- **THEN** `visits[level_id]` is created with `count = 1`
- **AND** `log` contains one entry with the provided `game_time_ms`, `from_level`, and `companions`

#### Scenario: Subsequent visit to a level
- **WHEN** `record_visit(level_id, game_time_ms, from_level, companions)` is called for a level with existing visits
- **THEN** `visits[level_id].count` is incremented by 1
- **AND** a new entry is appended to `visits[level_id].log`

#### Scenario: Visit with no companions
- **WHEN** `record_visit` is called with an empty companions list
- **THEN** the log entry's `companions` field SHALL be an empty table

### Requirement: Track from_level for transition detection

The levels store SHALL track which level the player was on before the current level, persisted across VM resets.

#### Scenario: Set from_level on visit
- **WHEN** `set_from_level(level_id)` is called
- **THEN** `levels.from_level` is updated to the provided `level_id`

#### Scenario: Get from_level
- **WHEN** `get_from_level()` is called
- **THEN** the current `levels.from_level` value is returned

#### Scenario: No from_level set (fresh game)
- **WHEN** `get_from_level()` is called before any level transition
- **THEN** `nil` is returned

### Requirement: Query visit count

The levels store SHALL provide the authoritative visit count for any level.

#### Scenario: Query visited level
- **WHEN** `get_visit_count(level_id)` is called for a level with recorded visits
- **THEN** the `count` value for that level is returned

#### Scenario: Query unvisited level
- **WHEN** `get_visit_count(level_id)` is called for a level with no visits
- **THEN** `0` is returned

### Requirement: Query visit log

The levels store SHALL provide access to the visit log for a given level.

#### Scenario: Get log for visited level
- **WHEN** `get_log(level_id)` is called for a level with recorded visits
- **THEN** the `log` array for that level is returned, ordered chronologically (oldest first)

#### Scenario: Get log for unvisited level
- **WHEN** `get_log(level_id)` is called for a level with no visits
- **THEN** an empty table is returned

### Requirement: Versioned save data with envelope pattern

The levels store SHALL persist using the envelope save pattern consistent with other domain stores.

#### Scenario: Save data structure
- **WHEN** `get_save_data()` is called
- **THEN** the returned table contains a `levels_version` field with value `1`
- **AND** the returned table contains a `levels` field with `from_level` and `visits` data

#### Scenario: Load versioned save data
- **GIVEN** saved_data = `{ levels_version = 1, levels = { from_level = "l01_escape", visits = { ... } } }`
- **WHEN** `load_save_data(saved_data)` is called
- **THEN** the store state is restored from `saved_data.levels`

#### Scenario: Load nil save data
- **GIVEN** saved_data is nil
- **WHEN** `load_save_data(saved_data)` is called
- **THEN** the store remains empty with no error

### Requirement: Legacy save data migration

The levels store SHALL migrate data from the old trigger script format on load.

#### Scenario: Migrate from legacy format
- **GIVEN** saved_data has no `levels_version` field
- **AND** saved_data contains `level_visit_count` (table of level → integer) and `from_level` (string)
- **WHEN** `load_save_data(saved_data)` is called
- **THEN** each `level_visit_count[level] = N` is migrated to `visits[level] = { count = N, log = {} }`
- **AND** `from_level` is restored
- **AND** a log message indicates legacy migration occurred

### Requirement: Pruning on save

The levels store SHALL support configurable pruning of visit log entries, applied during save.

#### Scenario: Pruning disabled (default)
- **GIVEN** max_log_entries_per_level config is `0`
- **WHEN** `get_save_data()` is called
- **THEN** all log entries for all levels are included in the save data

#### Scenario: Pruning enabled
- **GIVEN** max_log_entries_per_level config is `N` (N > 0)
- **AND** a level has more than `N` log entries
- **WHEN** `get_save_data()` is called
- **THEN** only the last `N` log entries are included for that level
- **AND** the `count` value is unchanged (authoritative, not derived from log length)

#### Scenario: Pruning config from MCM
- **WHEN** the store reads pruning config
- **THEN** it reads via `interface.config` getter, not directly from MCM

### Requirement: Clear store

The levels store SHALL support clearing all data.

#### Scenario: Clear all data
- **WHEN** `clear()` is called
- **THEN** all visits data is removed
- **AND** `from_level` is set to `nil`
