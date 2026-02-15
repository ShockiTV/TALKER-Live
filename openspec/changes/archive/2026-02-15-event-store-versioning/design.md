# Store Versioning - Design

## Overview

Add versioning to all store save data to enable safe migrations. Legacy saves (without version) will either migrate or start fresh depending on data complexity.

## Technical Approach

### Save Data Structure Pattern

Each store follows the same versioned structure pattern:

```lua
-- Before (legacy): just the raw data
return raw_data

-- After (versioned):
return {
    <store>_version = "2",
    <store> = raw_data,
}
```

### Event Store

**Before (legacy):**
```lua
return self.events
-- Result: { [1000] = event1, [2000] = event2, ... }
```

**After (versioned):**
```lua
return {
    events_version = "2",
    events = self.events,
}
```

**Migration:** Legacy → start fresh (events are transient)

### Memory Store

**Before (legacy):**
```lua
return narrative_memories
-- Result: { [char_id] = { narrative = "...", last_update_time_ms = N }, ... }
-- OR old format: { [char_id] = [ event1, event2, ... ], ... }
```

**After (versioned):**
```lua
return {
    memories_version = "2",
    memories = narrative_memories,
}
```

**Migration:** 
- Version 2 format → load directly
- No version + object format → treat as legacy v1, migrate inline
- No version + list format → old event list, trigger compression

### Backstories Store

**Before (legacy):**
```lua
return character_backstories
-- Result: { [char_id] = "bandit.3", ... } (new ID format)
-- OR: { [char_id] = "A long backstory text...", ... } (old text format)
```

**After (versioned):**
```lua
return {
    backstories_version = "2",
    backstories = character_backstories,
}
```

**Migration:** Legacy → clear (will be re-assigned on demand with new ID format)

### Personalities Store

**Before (legacy):**
```lua
return character_personalities
-- Result: { [char_id] = "bandit.3", ... }
```

**After (versioned):**
```lua
return {
    personalities_version = "2",
    personalities = character_personalities,
}
```

**Migration:** Legacy → clear (will be re-assigned on demand with new ID format)

### Version Strategy

- Version `"2"` is the first versioned format (version 1 is implicit for legacy)
- String type allows semantic versioning in future if needed
- Each store has its own version field to allow independent evolution

### Load Logic Pattern

```
load_save_data(saved_data)
├── saved_data is nil? → start fresh
├── saved_data.<store>_version exists?
│   ├── matches current VERSION? → load saved_data.<store>
│   └── unknown version? → start fresh (log warning)
└── no <store>_version? → legacy format → migrate or start fresh
```

## Files to Modify

| File | Change |
|------|--------|
| `bin/lua/domain/repo/event_store.lua` | Already versioned (v2) ✓ |
| `bin/lua/domain/repo/memory_store.lua` | Add memories_version, wrap in versioned structure |
| `bin/lua/domain/repo/backstories.lua` | Add backstories_version, remove string-length heuristic |
| `bin/lua/domain/repo/personalities.lua` | Add personalities_version |
| `tests/repo/test_event_store.lua` | Already has version tests ✓ |
| `tests/repo/test_memory_store.lua` | Add version tests |
| `tests/entities/test_backstories.lua` | Add version tests |
| `tests/entities/test_personalities.lua` | Add version tests |

## Testing Strategy

For each store:
1. Test saving produces versioned structure
2. Test loading versioned data
3. Test loading legacy data (no version) → appropriate migration
4. Test loading nil data → empty store
5. Test loading unknown version → empty store
