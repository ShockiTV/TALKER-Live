## ADDED Requirements

### Requirement: Timers store persistence

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
