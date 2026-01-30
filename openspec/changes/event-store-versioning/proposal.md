# Event Store Versioning

## Purpose

Add version tracking to event_store save data to enable future migrations. When loading saves without a version field, start fresh with an empty event store rather than failing. The field is named `events_version` to allow other data types to have their own version fields in the future.

## Requirements

### REQ-1: Add events_version field to save data structure

The event_store save data must include an events_version string field.

#### Scenario: Save data includes events_version

- WHEN event_store:get_save_data() is called
- THEN the returned table contains an "events_version" field with value "2"
- AND the returned table contains an "events" field with the events array

### REQ-2: Load versioned save data

When loading save data that contains an events_version field, load normally.

#### Scenario: Load save with events_version field

- GIVEN saved_data = { events_version = "2", events = [...] }
- WHEN event_store:load_save_data(saved_data) is called
- THEN events are loaded from saved_data.events
- AND the store functions normally

### REQ-3: Handle legacy saves without events_version

When loading save data without an events_version field (legacy format), start with empty store.

#### Scenario: Load legacy save without events_version

- GIVEN saved_data is a table without an "events_version" field (legacy format with just events array)
- WHEN event_store:load_save_data(saved_data) is called
- THEN the event store is cleared (empty)
- AND a log message indicates legacy save was detected

### REQ-4: Handle nil save data

When loading nil save data, start with empty store.

#### Scenario: Load nil save data

- GIVEN saved_data is nil
- WHEN event_store:load_save_data(saved_data) is called
- THEN the event store remains empty
- AND no error occurs

## Tasks

- [ ] Update event_store:get_save_data() to return { events_version = "2", events = events }
- [ ] Update event_store:load_save_data() to check for events_version field
- [ ] If events_version missing or unrecognized, clear store and log warning
- [ ] Add tests for versioned save/load
- [ ] Add tests for legacy save handling
