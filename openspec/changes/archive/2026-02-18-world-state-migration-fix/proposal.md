## Why

During the Lua→Python migration, the `world_state.lua` module was not migrated, causing dialogue prompts to lose critical world context: dead faction leaders, major world events (Brain Scorcher, Miracle Machine), regional politics (Cordon truce), and important/notable character deaths. This context is essential for immersive, lore-accurate NPC dialogue.

Additionally, the current architecture stores `world_context` per event (location, time, weather), but only the most recent event's context is ever used (for "CURRENT LOCATION" prompt section). This wastes storage and doesn't reflect the current scene.

## What Changes

- **Port important characters registry** to Python (`talker_service/`) - faction leaders, important NPCs, notable NPCs with their metadata (areas, descriptions, factions)
- **Add world state queries** - Lua queries game state (info portions, character alive status) and sends to Python via ZMQ state queries
- **Remove world_context from events** - No longer store per-event; query current scene JIT during prompt building
- **Consolidate scene query** - Single query returns structured data: `loc`, `poi`, `time` (object), `weather`, `emission`, `psy_storm`, `sheltering`, `campfire`, info portions
- **Add world context to dialogue prompts** - Python receives world state data and injects it into dialogue prompts:
  - Current location/scene context (queried JIT)
  - Dead faction leaders section
  - Dead important/notable characters section  
  - Major world events (Brain Scorcher disabled, Miracle Machine disabled)
  - Regional politics (Cordon truce when player is in Cordon)
- **Context-aware notable filtering** - Notable characters only shown if mentioned in recent events or relevant to current area
- **Remove dead Lua code** - Delete Lua functions migrated to Python that are now unused:
  - `Event.describe()`, `Event.describe_short()`, `Event.describe_event()`, `TEMPLATES` table
  - `game_adapter.get_mentioned_factions()`, `is_player_involved()`, `get_mentioned_characters()`

## Capabilities

### New Capabilities
- `python-world-context` - World state context builder for dialogue prompts

### Modified Capabilities
- `python-prompt-builder` - Add world context section to dialogue prompts
- `lua-state-query-handler` - Extend world context query with info portions, character alive status
- `lua-event-creation` - Remove world_context field from event creation
- `python-event-model` - Remove world_context field from Event model
- `lua-dead-code-removal` - Remove Lua functions now handled by Python

## Impact

**Python (`talker_service/`)**:
- New module `prompts/world_context.py` with important character registry and context builder
- Update `prompts/builder.py` to include world context in dialogue prompts (query JIT instead of reading from event)
- Update `prompts/models.py` to remove world_context from Event
- Update `state/models.py` for scene query response model

**Lua (`bin/lua/`, `gamedata/scripts/`)**:
- Update `talker_zmq_query_handlers.script` to extend `handle_world_context` with new fields
- Update `interface/interface.lua` to remove world_context from event creation
- Update `domain/model/event.lua` to remove world_context field and dead code (describe functions, TEMPLATES)
- Remove dead code from `game_adapter.lua` (mention scanning functions now in Python)
- May need helper in `talker_game_queries.script` for `has_alife_info()` and character alive checks

**Data flow**: 
- Events no longer carry world_context
- During prompt building: Python queries scene → Lua returns structured data → Python builds prompt sections
