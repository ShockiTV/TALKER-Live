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
