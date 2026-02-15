# Store Versioning - Tasks

## 1. Event Store (COMPLETE)

- [x] 1.1 Add EVENTS_VERSION constant to event_store.lua
- [x] 1.2 Update get_save_data() to return versioned structure { events_version, events }
- [x] 1.3 Update load_save_data() to handle versioned format
- [x] 1.4 Update load_save_data() to handle legacy format (no version) → empty store
- [x] 1.5 Update load_save_data() to handle nil data → empty store
- [x] 1.6 Update load_save_data() to handle unknown version → empty store with warning
- [x] 1.7 Add test for get_save_data() returns versioned structure
- [x] 1.8 Add test for load_save_data() with versioned data
- [x] 1.9 Add test for load_save_data() with legacy data
- [x] 1.10 Add test for load_save_data() with nil data
- [x] 1.11 Add test for load_save_data() with unknown version
- [x] 1.12 Run existing event_store tests to ensure no regressions

## 2. Memory Store

- [x] 2.1 Add MEMORIES_VERSION constant to memory_store.lua
- [x] 2.2 Update get_save_data() to return versioned structure { memories_version, memories }
- [x] 2.3 Update load_save_data() to handle versioned format
- [x] 2.4 Update load_save_data() to handle legacy format (no version) with migration
- [x] 2.5 Update load_save_data() to handle nil data → empty store
- [x] 2.6 Update load_save_data() to handle unknown version → empty store with warning
- [x] 2.7 Add test for get_save_data() returns versioned structure
- [x] 2.8 Add test for load_save_data() with versioned data
- [x] 2.9 Add test for load_save_data() with legacy data (object format)
- [x] 2.10 Add test for load_save_data() with legacy data (old list format)
- [x] 2.11 Add test for load_save_data() with nil data
- [x] 2.12 Add test for load_save_data() with unknown version
- [x] 2.13 Run existing memory_store tests to ensure no regressions

## 3. Backstories Store

- [x] 3.1 Add BACKSTORIES_VERSION constant to backstories.lua
- [x] 3.2 Update get_save_data() to return versioned structure { backstories_version, backstories }
- [x] 3.3 Update load_save_data() to handle versioned format
- [x] 3.4 Update load_save_data() to handle legacy format (no version) → clear store
- [x] 3.5 Remove string-length heuristic migration (replaced by version check)
- [x] 3.6 Update load_save_data() to handle nil data → empty store
- [x] 3.7 Update load_save_data() to handle unknown version → empty store with warning
- [x] 3.8 Add test for get_save_data() returns versioned structure
- [x] 3.9 Add test for load_save_data() with versioned data
- [x] 3.10 Add test for load_save_data() with legacy data
- [x] 3.11 Add test for load_save_data() with nil data
- [x] 3.12 Add test for load_save_data() with unknown version
- [x] 3.13 Run existing backstories tests to ensure no regressions

## 4. Personalities Store

- [x] 4.1 Add PERSONALITIES_VERSION constant to personalities.lua
- [x] 4.2 Update get_save_data() to return versioned structure { personalities_version, personalities }
- [x] 4.3 Update load_save_data() to handle versioned format
- [x] 4.4 Update load_save_data() to handle legacy format (no version) → clear store
- [x] 4.5 Update load_save_data() to handle nil data → empty store
- [x] 4.6 Update load_save_data() to handle unknown version → empty store with warning
- [x] 4.7 Add test for get_save_data() returns versioned structure
- [x] 4.8 Add test for load_save_data() with versioned data
- [x] 4.9 Add test for load_save_data() with legacy data
- [x] 4.10 Add test for load_save_data() with nil data
- [x] 4.11 Add test for load_save_data() with unknown version
- [x] 4.12 Run existing personalities tests to ensure no regressions

## 5. Final Validation

- [x] 5.1 Manual test: load old save file, verify all stores handle gracefully
