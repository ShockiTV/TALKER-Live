## MODIFIED Requirements

### Requirement: Config sync on load

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

## ADDED Requirements

### Requirement: Levels store persistence

The persistence hub SHALL save and load the levels store alongside other domain stores.

#### Scenario: Save includes level_visits
- **WHEN** `save_state(saved_data)` is called
- **THEN** `saved_data.levels` is set to `levels.get_save_data()`

#### Scenario: Load restores level_visits
- **GIVEN** `saved_data.levels` contains valid levels save data
- **WHEN** `load_state(saved_data)` is called
- **THEN** `levels.load_save_data(saved_data.levels)` is called

#### Scenario: Load with legacy map transition data
- **GIVEN** `saved_data.levels` is nil
- **AND** `saved_data` contains `level_visit_count` and `previous_map` from the old trigger script format
- **WHEN** `load_state(saved_data)` is called
- **THEN** the legacy data is passed to `levels.load_save_data()` for migration

#### Scenario: Load with no level visits data
- **GIVEN** `saved_data.levels` is nil and no legacy data exists
- **WHEN** `load_state(saved_data)` is called
- **THEN** the levels store remains empty with no error
