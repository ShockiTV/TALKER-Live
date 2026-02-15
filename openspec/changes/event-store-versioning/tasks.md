# Event Store Versioning - Tasks

## 1. Core Implementation

- [x] 1.1 Add EVENTS_VERSION constant to event_store.lua
- [x] 1.2 Update get_save_data() to return versioned structure { events_version, events }
- [x] 1.3 Update load_save_data() to handle versioned format
- [x] 1.4 Update load_save_data() to handle legacy format (no version) → empty store
- [x] 1.5 Update load_save_data() to handle nil data → empty store
- [x] 1.6 Update load_save_data() to handle unknown version → empty store with warning

## 2. Testing

- [x] 2.1 Add test for get_save_data() returns versioned structure
- [x] 2.2 Add test for load_save_data() with versioned data
- [x] 2.3 Add test for load_save_data() with legacy data (no version)
- [x] 2.4 Add test for load_save_data() with nil data
- [x] 2.5 Add test for load_save_data() with unknown version

## 3. Validation

- [x] 3.1 Run existing event_store tests to ensure no regressions
- [ ] 3.2 Manual test: load old save file, verify empty store warning
