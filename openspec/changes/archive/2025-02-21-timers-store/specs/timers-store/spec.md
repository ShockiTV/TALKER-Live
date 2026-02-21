# timers-store

## Purpose

Domain repository for persisting timer values across game saves. Holds the cumulative game time accumulator (used by `get_game_time_ms()`) and the idle conversation check timer.

## Requirements

### Requirement: Store game time accumulator

The timers store SHALL hold a game time accumulator value that represents cumulative game time in milliseconds across all save/load cycles.

#### Scenario: Get accumulator after load
- **WHEN** `timers.get_game_time_accumulator()` is called after a successful `load_save_data`
- **THEN** the previously persisted accumulator value is returned

#### Scenario: Get accumulator on fresh state
- **WHEN** `timers.get_game_time_accumulator()` is called with no prior load
- **THEN** `0` is returned

#### Scenario: Accumulator is read-only during gameplay
- **GIVEN** the timers store has loaded an accumulator value
- **WHEN** gameplay is in progress
- **THEN** no public setter exists for the accumulator — it is only updated via `get_save_data(current_game_time_ms)`

### Requirement: Store idle last check time

The timers store SHALL hold the idle conversation check timer as a millisecond timestamp.

#### Scenario: Get idle check time after load
- **WHEN** `timers.get_idle_last_check_time()` is called after a successful `load_save_data`
- **THEN** the previously persisted idle check time is returned

#### Scenario: Set idle check time during gameplay
- **WHEN** `timers.set_idle_last_check_time(value)` is called with a numeric value
- **THEN** the stored idle check time is updated to that value

#### Scenario: Get idle check time on fresh state
- **WHEN** `timers.get_idle_last_check_time()` is called with no prior load
- **THEN** `0` is returned

### Requirement: Clear all state

The timers store SHALL support clearing all stored data to a fresh state.

#### Scenario: Clear resets all values
- **WHEN** `timers.clear()` is called
- **THEN** `get_game_time_accumulator()` returns `0`
- **AND** `get_idle_last_check_time()` returns `0`

### Requirement: Versioned save data with envelope pattern

The timers store SHALL persist using the envelope save pattern consistent with other domain stores.

#### Scenario: Save data structure
- **WHEN** `timers.get_save_data(current_game_time_ms)` is called
- **THEN** the returned table contains a `timers_version` field with value `1`
- **AND** the returned table contains a `timers` field with `game_time_accumulator` set to `current_game_time_ms`
- **AND** the `timers` field contains `idle_last_check_time` set to the current stored value

#### Scenario: Save snapshot uses passed-in time
- **GIVEN** `current_game_time_ms` is `500000`
- **AND** the stored idle check time is `123000`
- **WHEN** `timers.get_save_data(500000)` is called
- **THEN** the returned table is `{ timers_version = 1, timers = { game_time_accumulator = 500000, idle_last_check_time = 123000 } }`

#### Scenario: Load versioned save data
- **GIVEN** saved_data = `{ timers_version = 1, timers = { game_time_accumulator = 500000, idle_last_check_time = 123000 } }`
- **WHEN** `timers.load_save_data(saved_data)` is called
- **THEN** `get_game_time_accumulator()` returns `500000`
- **AND** `get_idle_last_check_time()` returns `123000`

#### Scenario: Load nil save data
- **GIVEN** saved_data is nil
- **WHEN** `timers.load_save_data(saved_data)` is called
- **THEN** the store is cleared to fresh state
- **AND** no error occurs

#### Scenario: Load unknown version
- **GIVEN** saved_data has `timers_version` set to an unrecognized value
- **WHEN** `timers.load_save_data(saved_data)` is called
- **THEN** the store is cleared to fresh state
- **AND** a warning is logged

### Requirement: Legacy save data migration

The timers store SHALL migrate data from the old inline-persisted format on load.

#### Scenario: Migrate legacy game time key
- **GIVEN** saved_data has no `timers_version` field
- **AND** saved_data contains `game_time_since_last_load = 500000`
- **WHEN** `timers.load_save_data(saved_data)` is called
- **THEN** `get_game_time_accumulator()` returns `500000`
- **AND** a log message indicates legacy migration occurred

#### Scenario: Migrate legacy idle timer key
- **GIVEN** saved_data has no `timers_version` field
- **AND** saved_data contains `talker_idle_last_check_time_ms = 123000`
- **WHEN** `timers.load_save_data(saved_data)` is called
- **THEN** `get_idle_last_check_time()` returns `123000`

#### Scenario: Migrate with partial legacy data
- **GIVEN** saved_data has no `timers_version` field
- **AND** saved_data contains `game_time_since_last_load = 500000` but no `talker_idle_last_check_time_ms`
- **WHEN** `timers.load_save_data(saved_data)` is called
- **THEN** `get_game_time_accumulator()` returns `500000`
- **AND** `get_idle_last_check_time()` returns `0`
