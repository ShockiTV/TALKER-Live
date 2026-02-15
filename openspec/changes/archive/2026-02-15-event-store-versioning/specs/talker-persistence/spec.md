# talker-persistence delta

## ADDED Requirements

### Requirement: Event store versioning

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

### Requirement: Memory store versioning

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

### Requirement: Backstories store versioning

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

### Requirement: Personalities store versioning

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
