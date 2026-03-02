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

### Memory store versioning

The memory_store persistence format SHALL use version 3 (v3). Format:

```
{
  "version": 3,
  "characters": {
    "<character_id>": {
      "events": [ {seq, timestamp, type, context}, ... ],
      "summaries": [ {seq, tier, start_ts, end_ts, text, source_count}, ... ],
      "digests": [ {seq, tier, start_ts, end_ts, text, source_count}, ... ],
      "cores": [ {seq, tier, start_ts, end_ts, text, source_count}, ... ],
      "background": { text, updated_ts } | null,
      "next_seq": <integer>
    }
  }
}
```

#### Scenario: v3 save
- **WHEN** memory_store:save() is called with 2 characters
- **THEN** saved JSON SHALL have `"version": 3` and the `characters` object with per-character tiers

#### Scenario: v3 load
- **WHEN** loading a v3 save file with 2 characters
- **THEN** each character's tiers SHALL be restored with correct seq numbers

#### Scenario: v2 → v3 migration
- **WHEN** loading a v2 memory_store save (`{version: 2, characters: {id: {narrative, last_update_time_ms}}}`)
- **THEN** the narrative text SHALL be placed into `cores[0]` as `{seq: 0, tier: "core", start_ts: 0, end_ts: last_update_time_ms, text: narrative, source_count: 0}`
- **AND** all other tiers SHALL be empty arrays
- **AND** `next_seq` SHALL be 1

#### Scenario: v1 format migration
- **WHEN** loading a v1 memory_store save (flat key-value without version)
- **THEN** each entry SHALL be migrated through v1→v2→v3 chain

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