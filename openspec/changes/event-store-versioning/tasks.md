# Event Store Versioning - Tasks

## 1. Core Implementation

- [ ] 1.1 Add EVENTS_VERSION constant to event_store.lua
- [ ] 1.2 Update get_save_data() to return versioned structure { events_version, events }
- [ ] 1.3 Update load_save_data() to handle versioned format
- [ ] 1.4 Update load_save_data() to handle legacy format (no version) → empty store
- [ ] 1.5 Update load_save_data() to handle nil data → empty store
- [ ] 1.6 Update load_save_data() to handle unknown version → empty store with warning

## 2. Testing

- [ ] 2.1 Add test for get_save_data() returns versioned structure
- [ ] 2.2 Add test for load_save_data() with versioned data
- [ ] 2.3 Add test for load_save_data() with legacy data (no version)
- [ ] 2.4 Add test for load_save_data() with nil data
- [ ] 2.5 Add test for load_save_data() with unknown version

## 3. Validation

- [ ] 3.1 Run existing event_store tests to ensure no regressions
- [ ] 3.2 Manual test: load old save file, verify empty store warning
