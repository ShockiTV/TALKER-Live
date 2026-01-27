# Event Store Enum Refactor

## Problem Statement

Currently, events are stored with pre-formatted description strings like:
```lua
description = "Anonsky (Veteran stalker, Good rep) was killed by Wolf (Master Duty, Great rep)!"
```

This approach has issues:
- **Large memory footprint**: Verbose strings stored for every event
- **No queryability**: Can't filter events by type without string parsing
- **Rigid formatting**: Can't change how events display without regenerating all stored data
- **Redundant flags**: `is_death`, `is_artifact`, etc. duplicate information that could be a single type field

## Proposed Solution

Replace `description` string with structured `type` enum + `context` object:

```lua
-- BEFORE
{
  description = "Anonsky (Veteran stalker) was killed by Wolf!",
  involved_objects = [Character{...}, Character{...}],
  flags = { is_death = true, is_silent = true }
}

-- AFTER  
{
  type = EventType.DEATH,
  context = {
    victim = Character{...},
    killer = Character{...},
  },
  flags = { is_silent = true }  -- is_death removed (redundant)
}
```

Text resolution happens at the edges via `Event.describe(event)` when needed for display or LLM prompts.

## Scope

### In Scope
- Event model refactor (`domain/model/event.lua`)
- EventType enum definition
- Template-based `Event.describe()` function
- `Event.get_involved_characters()` helper to extract characters from context
- All trigger scripts migration to new event format
- Listener/interface layer updates

### Out of Scope (for now)
- Memory store changes (keeps working with resolved strings)
- Migration of existing save data (accepting data loss, fresh start)
- `content` field (used by compressed memories, unchanged)

## Design Decisions

1. **Context uses named references** (not indices): `context.killer` instead of `context.killer_idx` pointing to `involved_objects[1]`

2. **Dialogue events keep text in context**: `{ speaker, text }` since dialogue text is user/LLM generated, not template-able

3. **Template resolution in Event model**: `Event.describe(event)` method, not a separate resolver module

4. **Flags simplified**: Type-based flags (`is_death`, `is_artifact`) removed; behavioral flags kept (`is_silent`, `is_compressed`, `is_synthetic`)

5. **`involved_objects` deprecated**: Replaced by `Event.get_involved_characters(event)` that extracts from context dynamically

## Migration Strategy

- Start with simplest trigger (`weapon_jam`) to prove the model
- Migrate triggers one at a time
- Accept data loss on existing saves (fresh event store)

## Success Criteria

- All triggers produce typed events
- Events can be filtered by type
- `Event.describe()` produces equivalent text to old format strings
- Memory compression continues working (receives resolved strings)
- No increase in code complexity at trigger sites
