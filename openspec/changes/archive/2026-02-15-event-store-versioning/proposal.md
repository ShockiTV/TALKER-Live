# Store Versioning

## Purpose

Add version tracking to all store save data to enable future migrations. When loading saves without a version field, apply appropriate migration or start fresh. Each store has its own version field (e.g., `events_version`, `memories_version`, `backstories_version`, `personalities_version`).

## Requirements

### REQ-1: Event Store Versioning

Add events_version field to event_store save data.

#### Scenario: Save data includes events_version

- WHEN event_store:get_save_data() is called
- THEN the returned table contains an "events_version" field with value "2"
- AND the returned table contains an "events" field with the events array

#### Scenario: Load legacy save without events_version

- GIVEN saved_data is a table without an "events_version" field
- WHEN event_store:load_save_data(saved_data) is called
- THEN the event store is cleared (empty)
- AND a log message indicates legacy save was detected

### REQ-2: Memory Store Versioning

Add memories_version field to memory_store save data.

#### Scenario: Save data includes memories_version

- WHEN memory_store:get_save_data() is called
- THEN the returned table contains a "memories_version" field with value "2"
- AND the returned table contains a "memories" field with the narrative memories

#### Scenario: Load legacy save without memories_version

- GIVEN saved_data is a table without a "memories_version" field (old list format)
- WHEN memory_store:load_save_data(saved_data) is called
- THEN existing inline migration logic triggers
- AND log message indicates legacy save was detected

### REQ-3: Backstories Store Versioning

Add backstories_version field to backstories save data.

#### Scenario: Save data includes backstories_version

- WHEN backstories.get_save_data() is called
- THEN the returned table contains a "backstories_version" field with value "2"
- AND the returned table contains a "backstories" field with the character backstory IDs

#### Scenario: Load legacy save without backstories_version

- GIVEN saved_data is a table without a "backstories_version" field
- WHEN backstories.load_save_data(saved_data) is called
- THEN character backstories are cleared (will be re-assigned on demand)
- AND log message indicates migration from old format

### REQ-4: Personalities Store Versioning

Add personalities_version field to personalities save data.

#### Scenario: Save data includes personalities_version

- WHEN personalities.get_save_data() is called
- THEN the returned table contains a "personalities_version" field with value "2"
- AND the returned table contains a "personalities" field with the character personality IDs

#### Scenario: Load legacy save without personalities_version

- GIVEN saved_data is a table without a "personalities_version" field
- WHEN personalities.load_save_data(saved_data) is called
- THEN character personalities are cleared (will be re-assigned on demand)
- AND log message indicates migration from old format

### REQ-5: Handle nil save data

When loading nil save data for any store, start with empty store.

#### Scenario: Load nil save data

- GIVEN saved_data is nil
- WHEN any store's load_save_data(saved_data) is called
- THEN the store remains empty
- AND no error occurs

## Tasks

### Event Store (DONE)
- [x] Update event_store:get_save_data() to return { events_version = "2", events = events }
- [x] Update event_store:load_save_data() to check for events_version field
- [x] Add tests for versioned save/load

### Memory Store
- [ ] Update memory_store:get_save_data() to return { memories_version = "2", memories = memories }
- [ ] Update memory_store:load_save_data() to check for memories_version field
- [ ] Keep existing inline migration for old list format
- [ ] Add tests for versioned save/load

### Backstories Store
- [ ] Update backstories.get_save_data() to return { backstories_version = "2", backstories = cache }
- [ ] Update backstories.load_save_data() to check for backstories_version field
- [ ] Remove string-length heuristic migration (replaced by version check)
- [ ] Add tests for versioned save/load

### Personalities Store
- [ ] Update personalities.get_save_data() to return { personalities_version = "2", personalities = cache }
- [ ] Update personalities.load_save_data() to check for personalities_version field
- [ ] Add tests for versioned save/load
