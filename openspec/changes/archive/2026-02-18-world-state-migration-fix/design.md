# Design: World State Migration Fix

## Context

The TALKER-fork codebase contains `world_state.lua` (454 lines) which provides rich world context for dialogue generation:
- **Info portions**: Major events like Brain Scorcher disabled, Miracle Machine destroyed
- **Important characters registry**: ~30 characters with roles (Leader, Important, Notable), factions, areas, descriptions
- **Death tracking**: Checks `sobj:alive()` for each character to identify dead faction leaders and important NPCs
- **Context-aware filtering**: Notable characters only shown if mentioned in recent events or player is in their area
- **Regional politics**: Cordon truce shown when player is in l01_escape

This functionality was NOT migrated to TALKER-Expanded. The current `handle_world_context` query handler returns only:
- location, location_technical, nearby_smart_terrain
- time_of_day, weather, emission, game_time_ms

The Python `WorldContext` model in `state/models.py` mirrors this limited structure.

## Goals

1. **Restore world state context** - Dead leaders, important character deaths, major events, regional politics
2. **Preserve existing functionality** - Current world context fields must continue to work
3. **Maintain clean separation** - Lua handles game queries, Python handles prompt building
4. **Enable context-aware filtering** - Notable deaths filtered by relevance to current context
5. **Remove redundant per-event storage** - Query current scene JIT instead of storing world_context per event

## Non-Goals

1. **Real-time alive/dead caching** - Always query current state, no persistent tracking
2. **Faction relation changes** - Not tracking dynamic disposition shifts
3. **Complete character registry** - Only important/notable characters, not all NPCs
4. **Player-specific world state** - No tracking of player reputation effects on world

## Decisions

### D1: Store important characters registry in Python, query alive status from Lua

**Options considered:**
- A) Store important_characters registry in Python, query alive status separately
- B) Keep registry in Lua, return filtered dead characters in query response
- C) Hybrid: Python stores static metadata, Lua queries alive status

**Decision: Option A** - Store important characters registry in Python, query alive status from Lua

**Rationale:**
- Important character metadata (names, roles, factions, descriptions, areas) is static data
- Python already has patterns for static lookup tables (`texts/personality/`, `texts/backstory/`)
- Query becomes simple: send list of story IDs, get back alive/dead status
- Lua handler stays thin - just resolves IDs and checks alive status
- Filtering logic stays in Python where context (recent events, prompt building) already lives

### D2: Add new query for character alive status

**Options considered:**
- A) Extend existing `state.query.world` to include all world state fields
- B) Add new `state.query.characters_alive` query that takes IDs as input
- C) Multiple separate queries for each category

**Decision: Option B** - Add new query for alive status checks

**Rationale:**
- Existing world query returns fixed data (location, time, weather)
- New query has different shape: takes list of IDs, returns alive/dead status map
- Clean separation of concerns
- Python decides which IDs to query based on context

### D3: Python filters important characters to query and filters results

**Options considered:**
- A) Python sends recent events with query, Lua applies filtering
- B) Lua queries event_store directly (already has access)
- C) Python receives all dead characters, applies filtering itself

**Decision: Option C** - Python handles all filtering

**Rationale:**
- Python has full context: recent events, current dialogue, prompt building state
- Python selects which important character IDs to query based on relevance
- Lua returns simple alive/dead map for requested IDs
- Python filters and formats results for prompt injection
- Clean separation: Lua = game state access, Python = logic and filtering

### D4: Return structured data, not formatted strings

**Options considered:**
- A) Return pre-formatted markdown strings (like fork's `get_world_state_context()`)
- B) Return structured data, let Python build prompt sections

**Decision: Option B** - Return structured data

**Rationale:**
- Consistent with existing pattern (Python builds all prompts)
- Allows Python to customize formatting
- Easier to test (structured data vs string parsing)
- More flexible for future prompt changes

### D5: Create important_characters registry in Python texts/

**Decision:** Create `texts/characters/important.py` with character registry (roles, IDs, factions, areas, descriptions)

**Rationale:**
- Follows existing pattern (`texts/personality/`, `texts/backstory/`)
- Static metadata belongs with other lookup data in Python
- Easy to maintain and test without game dependencies
- World state builder in `prompts/` can import directly

### D6: Extend world context query with info portions

**Decision:** Add `brain_scorcher_disabled` and `miracle_machine_disabled` booleans to existing `state.query.world` response

**Rationale:**
- No input parameters needed (just check `has_alife_info()`)
- Fits naturally in world context query (global world state)
- Avoids additional ZMQ round-trip

### D7: Remove world_context from event storage, query JIT for prompts

**Options considered:**
- A) Keep `world_context` per event (current approach in fork)
- B) Remove from events, query current scene JIT during prompt building
- C) Hybrid: store minimal ID, fetch full data JIT

**Decision: Option B** - Remove from events, query current scene JIT

**Rationale:**
- Fork only uses `new_events[#new_events].world_context` (most recent event, line 919-920 of `prompt_builder.lua`)
- The "CURRENT LOCATION" prompt section needs current player position, not historical event positions
- All other events in the prompt don't need their world_context at all
- Storing per-event wastes space and doesn't reflect current scene
- Query includes: `loc`, `poi`, `time` (as object), `weather`, `emission`, `psy_storm`, `sheltering`, `campfire`
- Time format: `{Y, M, D, h, m, s, ms}` object for easy field access

**Impact:**
- Remove `world_context` field from Event entity
- Remove `world_context` from `interface.lua` event creation
- Modify Python prompt builder to query current scene instead of reading from event
- Update tests that mock event.world_context

### D8: Consolidate existing world.context query with new scene data

**Decision:** Rename/extend `state.query.world` to serve as the comprehensive scene query

**Fields in response:**
```python
{
    "loc": "l01_escape",                    # location_technical
    "poi": "Rookie Village",                # nearby_smart_terrain (can be null)
    "time": {                               # game time as object
        "Y": 2012,
        "M": 9,
        "D": 15,
        "h": 8,
        "m": 30,
        "s": 45,
        "ms": 123
    },
    "weather": "cloudy",
    "emission": false,                      # emission active
    "psy_storm": false,                     # psi storm active
    "sheltering": false,                    # player is sheltered
    "campfire": "lit",                      # near campfire: null, "lit", or "unlit"
    "brain_scorcher_disabled": false,       # from D6
    "miracle_machine_disabled": false       # from D6
}
```

**Rationale:**
- Single ZMQ query for all scene context
- Clean field names (short, unambiguous)
- Booleans for emission/psy_storm (split from string)
- Time as array instead of formatted string
- Campfire status for immersion

## Risks and Trade-offs

### R1: Performance of alive checks on every query

**Risk:** Checking ~30 characters' alive status on every world context query may be slow

**Mitigation:**
- `get_story_object()` is a fast ID lookup
- Only called during dialogue generation (not every frame)
- Can optimize later with caching if needed (non-goal for now)

### R2: Story ID changes across Anomaly versions

**Risk:** Character IDs like `bar_dolg_leader` may change in game updates

**Mitigation:**
- Use `ids` list pattern (already in fork) to handle multiple possible IDs per character
- Python registry stores all known ID variants
- Document known ID variations
- Accept this is a maintenance task when game updates

### R3: Info portion availability

**Risk:** Info portions like `INFO_BRAIN_SCORCHER_DEAD` may not be set in all game scenarios

**Mitigation:**
- Use `has_alife_info()` which returns false if not set
- Graceful degradation (just don't show that section)

### R4: Increased ZMQ response size

**Risk:** Adding dead characters and world events increases response payload

**Mitigation:**
- Text payload is small (~1KB max for worst case)
- ZMQ handles this efficiently
- Negligible compared to LLM API calls

### R5: Breaking changes from removing world_context from events

**Risk:** Existing tests and code patterns depend on `event.world_context`

**Mitigation:**
- Field is not currently used in Python prompts (only stored)
- Tests that mock events need updating
- Lua-side event creation simplified (remove one field)
- Backwards compatible: old saved events with world_context field are harmless (just ignored)

### D9: Remove dead Lua code migrated to Python

**Decision:** Delete Lua functions that are now handled by Python and have no callers in TALKER-Expanded

**Functions to remove from `event.lua`:**
- `Event.describe()` - event-to-text rendering now in Python
- `Event.describe_short()` - wrapper for describe()
- `Event.describe_event()` - legacy event rendering
- `TEMPLATES` table - typed event templates
- `describe_object()` helper function
- `table_to_args()` helper function

**Functions to remove from `game_adapter.lua`:**
- `get_mentioned_factions(events)` - faction mention scanning now in Python
- `is_player_involved(events, player_name)` - player involvement check now in Python
- `get_mentioned_characters(events, current_location, notable_characters)` - character mention filtering now in Python

**Rationale:**
- These functions exist only because they were copied from fork's `prompt_builder.lua`
- In Phase 2+ architecture, Python handles all prompt building
- Search confirms no production callers in TALKER-Expanded
- Fork still uses these (unchanged by this migration)
- Reduces maintenance burden and confusion about where logic lives

### D10: Clean up legacy Event model fields and consolidate models

**Decision:** Remove legacy `content` field, consolidate duplicate model definitions, modernize COMPRESSED event handling

**Changes:**
1. **Remove `Event.content` field** - Legacy field was used for compressed event summaries. COMPRESSED events now use `context.narrative` field.
2. **Consolidate models** - `prompts/models.py` now imports Character, Event, MemoryContext from `state/models.py` instead of defining duplicates
3. **Remove `is_synthetic` property** - Was used to identify time gap events. Now using `NarrativeCue` dataclass for transient prompt items.
4. **Remove `is_compressed` handling** - Builder.py no longer skips events based on is_compressed flag. COMPRESSED events detected by type.
5. **Add `NarrativeCue` dataclass** - Prompt-only artifact for time gaps, not stored in event store
6. **Add COMPRESSED event type handler** - `helpers.py` handles `type="COMPRESSED"` by reading `context.narrative`

**Rationale:**
- Single source of truth for model definitions (state/models.py)
- Legacy flags no longer needed with typed event system
- COMPRESSED events use same pattern as other typed events (by type, not flag)
- NarrativeCue separates transient prompt artifacts from stored events
