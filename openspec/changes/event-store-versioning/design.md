# Event Store Versioning - Design

## Overview

Add versioning to event_store save data to enable safe migrations. Legacy saves (without version) will start fresh.

## Technical Approach

### Save Data Structure

**Before (legacy):**
```lua
-- get_save_data() returned just the events map
return self.events
-- Result: { [1000] = event1, [2000] = event2, ... }
```

**After (versioned):**
```lua
return {
    events_version = "2",
    events = self.events,
}
-- Result: { events_version = "2", events = { [1000] = event1, ... } }
```

### Version Strategy

- Version `"2"` is the first versioned format (version 1 is implicit for legacy)
- String type allows semantic versioning in future if needed
- Field named `events_version` (not `version`) to allow other data types to have their own version fields

### Load Logic

```
load_save_data(saved_data)
├── saved_data is nil? → start fresh
├── saved_data.events_version exists?
│   ├── matches EVENTS_VERSION? → load saved_data.events
│   └── unknown version? → start fresh (log warning)
└── no events_version? → legacy format → start fresh (log warning)
```

### Migration Path

- No data migration attempted
- Legacy saves simply start with empty event store
- This is acceptable because events are transient memories, not critical game state

## Files to Modify

| File | Change |
|------|--------|
| `bin/lua/domain/repo/event_store.lua` | Add versioning to get_save_data() and load_save_data() |
| `tests/repo/test_event_store.lua` | Add tests for versioned save/load |

## Testing Strategy

1. Test saving produces versioned structure
2. Test loading versioned data
3. Test loading legacy data (no version) → empty store
4. Test loading nil data → empty store
5. Test loading unknown version → empty store
