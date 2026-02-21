# talker-persistence

## Purpose

Game save/load persistence for TALKER Expanded, including memory stores and configuration sync.

## Requirements

### Config sync on load

The persistence module SHALL trigger a config sync to Python after loading game state.

#### Scenario: Load triggers delayed sync
- **WHEN** `load_state(saved_data)` completes successfully
- **THEN** a delayed config sync is scheduled for 2 seconds later

#### Scenario: Sync uses config_sync module
- **WHEN** the delayed sync timer fires
- **THEN** `lua_config_sync.publish_full_config()` is called

#### Scenario: Load without Python service
- **WHEN** game is loaded but Python service is not running
- **THEN** the sync attempt fails silently (fire-and-forget)

### ZMQ shutdown on game end

The persistence module SHALL clean up ZMQ resources when the game ends.

#### Scenario: Shutdown on game end
- **WHEN** `on_game_end` callback is invoked
- **THEN** `zmq_bridge.shutdown()` is called to clean up resources

#### Scenario: Shutdown idempotent
- **WHEN** `zmq_bridge.shutdown()` is called multiple times
- **THEN** no errors occur (idempotent operation)

### Event store versioning

The event_store SHALL include version tracking in save data to enable future migrations.

#### Scenario: Save data includes events_version
- **WHEN** `event_store:get_save_data()` is called
- **THEN** the returned table contains an `events_version` field with value `"2"`
- **AND** the returned table contains an `events` field with the events array

#### Scenario: Load save with events_version field
- **GIVEN** saved_data = `{ events_version = "2", events = [...] }`
- **WHEN** `event_store:load_save_data(saved_data)` is called
- **THEN** events are loaded from `saved_data.events`

#### Scenario: Load legacy save without events_version
- **GIVEN** saved_data is a table without an `events_version` field
- **WHEN** `event_store:load_save_data(saved_data)` is called
- **THEN** the event store is cleared (empty)
- **AND** a log message indicates legacy save was detected

#### Scenario: Load nil save data
- **GIVEN** saved_data is nil
- **WHEN** `event_store:load_save_data(saved_data)` is called
- **THEN** the event store remains empty
- **AND** no error occurs

### Memory store versioning

The memory_store SHALL include version tracking in save data to enable future migrations.

#### Scenario: Save data includes memories_version
- **WHEN** `memory_store:get_save_data()` is called
- **THEN** the returned table contains a `memories_version` field with value `"2"`
- **AND** the returned table contains a `memories` field with the narrative memories

#### Scenario: Load save with memories_version field
- **GIVEN** saved_data = `{ memories_version = "2", memories = {...} }`
- **WHEN** `memory_store:load_save_data(saved_data)` is called
- **THEN** memories are loaded from `saved_data.memories`

#### Scenario: Load legacy save without memories_version (object format)
- **GIVEN** saved_data is a table without a `memories_version` field (new object format)
- **WHEN** `memory_store:load_save_data(saved_data)` is called
- **THEN** legacy migration is applied
- **AND** a log message indicates legacy save was detected

#### Scenario: Load legacy save without memories_version (list format)
- **GIVEN** saved_data is a table without a `memories_version` field (old list format)
- **WHEN** `memory_store:load_save_data(saved_data)` is called
- **THEN** old event lists are migrated to narrative format
- **AND** a log message indicates migration

#### Scenario: Load nil save data
- **GIVEN** saved_data is nil
- **WHEN** `memory_store:load_save_data(saved_data)` is called
- **THEN** the memory store remains empty
- **AND** no error occurs

### Backstories store versioning

The backstories store SHALL include version tracking in save data to enable future migrations.

#### Scenario: Save data includes backstories_version
- **WHEN** `backstories.get_save_data()` is called
- **THEN** the returned table contains a `backstories_version` field with value `"2"`
- **AND** the returned table contains a `backstories` field with character backstory IDs

#### Scenario: Load save with backstories_version field
- **GIVEN** saved_data = `{ backstories_version = "2", backstories = {...} }`
- **WHEN** `backstories.load_save_data(saved_data)` is called
- **THEN** backstories are loaded from `saved_data.backstories`

#### Scenario: Load legacy save without backstories_version
- **GIVEN** saved_data is a table without a `backstories_version` field
- **WHEN** `backstories.load_save_data(saved_data)` is called
- **THEN** the backstories store is cleared (will be re-assigned on demand)
- **AND** a log message indicates legacy save was detected

#### Scenario: Load nil save data
- **GIVEN** saved_data is nil
- **WHEN** `backstories.load_save_data(saved_data)` is called
- **THEN** the backstories store remains empty
- **AND** no error occurs

### Personalities store versioning

The personalities store SHALL include version tracking in save data to enable future migrations.

#### Scenario: Save data includes personalities_version
- **WHEN** `personalities.get_save_data()` is called
- **THEN** the returned table contains a `personalities_version` field with value `"2"`
- **AND** the returned table contains a `personalities` field with character personality IDs

#### Scenario: Load save with personalities_version field
- **GIVEN** saved_data = `{ personalities_version = "2", personalities = {...} }`
- **WHEN** `personalities.load_save_data(saved_data)` is called
- **THEN** personalities are loaded from `saved_data.personalities`

#### Scenario: Load legacy save without personalities_version
- **GIVEN** saved_data is a table without a `personalities_version` field
- **WHEN** `personalities.load_save_data(saved_data)` is called
- **THEN** the personalities store is cleared (will be re-assigned on demand)
- **AND** a log message indicates legacy save was detected

#### Scenario: Load nil save data
- **GIVEN** saved_data is nil
- **WHEN** `personalities.load_save_data(saved_data)` is called
- **THEN** the personalities store remains empty
- **AND** no error occurs

### Levels store persistence

The persistence hub SHALL save and load the levels store alongside other domain stores.

#### Scenario: Save includes levels
- **WHEN** `save_state(saved_data)` is called
- **THEN** `saved_data.levels` is set to `levels.get_save_data()`

#### Scenario: Load restores levels
- **GIVEN** `saved_data.levels` contains valid levels save data
- **WHEN** `load_state(saved_data)` is called
- **THEN** `levels.load_save_data(saved_data.levels)` is called

#### Scenario: Load with legacy map transition data
- **GIVEN** `saved_data.levels` is nil
- **AND** `saved_data` contains `level_visit_count` and `previous_map` from the old trigger script format
- **WHEN** `load_state(saved_data)` is called
- **THEN** the legacy data is passed to `levels.load_save_data()` for migration

#### Scenario: Load with no levels data
- **GIVEN** `saved_data.levels` is nil and no legacy data exists
- **WHEN** `load_state(saved_data)` is called
- **THEN** the levels store remains empty with no error

### Timers store persistence

The persistence hub SHALL save and load the timers store alongside other domain stores.

#### Scenario: Save includes timers
- **WHEN** `save_state(saved_data)` is called
- **THEN** `saved_data.timers` is set to `timers.get_save_data(current_game_time_ms)` where `current_game_time_ms` is obtained from `talker_game_queries.get_game_time_ms()`

#### Scenario: Load restores timers
- **GIVEN** `saved_data.timers` contains valid timers save data
- **WHEN** `load_state(saved_data)` is called
- **THEN** `timers.load_save_data(saved_data.timers)` is called

#### Scenario: Load with legacy inline timer keys
- **GIVEN** `saved_data.timers` is nil
- **AND** `saved_data` contains `game_time_since_last_load` or `talker_idle_last_check_time_ms` from old inline callbacks
- **WHEN** `load_state(saved_data)` is called
- **THEN** the legacy keys are passed to `timers.load_save_data()` for migration

#### Scenario: Load with no timers data
- **GIVEN** `saved_data.timers` is nil and no legacy timer keys exist
- **WHEN** `load_state(saved_data)` is called
- **THEN** `timers.load_save_data(nil)` is called
- **AND** the timers store starts fresh with no error