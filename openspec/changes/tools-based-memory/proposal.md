## Why

The current dialogue system makes 2 LLM calls per event (speaker selection + dialogue generation) and stores NPC memory as a single flat narrative blob per character. This doubles API cost and latency, loses structured event detail through premature summarization, and limits memory capacity to ~24 events before compression destroys granularity. The new architecture halves LLM cost per event, preserves 500+ events of structured history per NPC in ~72 KB, and makes speaker selection contextual by providing the LLM with personality traits and memory access in a single tool-calling turn.

## What Changes

- **Lua memory store rewrite**: Replace flat `{narrative, last_update_time_ms}` per character with four-tier structured storage: `events[100] → summary[10] → digest[5] → core[5]` plus an optional `Background` (traits, backstory, connections). Per-NPC append-only event lists with sequential IDs.
- **Event fan-out in Lua**: When an event occurs, Lua appends structured event data to each witness NPC's memory store directly (no WS roundtrip). Global events (emissions) dual-write to existing NPCs + a backfill buffer for future encounters.
- **Unified store operations DSL**: Single `memory_store` module with `append/delete/set/update/query` verbs, called both locally (by triggers) and remotely (by Python via new `state.mutate.batch` WS topic).
- **New `state.mutate.batch` WS topic**: Batched write operations from Python → Lua for compaction results, background writes, trait evolution. ID-based deletes eliminate race conditions.
- **Tool-based dialogue generation**: Replace the 2-call flow (speaker selection LLM call + dialogue LLM call) with a single `ConversationManager` turn. The LLM receives event + candidate traits in one message and uses tools (`get_memories`, `background`, `get_character_info`) to read memory and generate dialogue. **BREAKING**: `SpeakerSelector` class and all `create_*_prompt()` functions are removed.
- **Compaction cascade**: Four-tier LLM-driven compression (10 events → 1 summary, 2 summaries → 1 digest, 2 digests → 1 core, 2 cores → 1 core). Budget-pool batch trigger. Uses fast/cheap model independently configurable from dialogue model.
- **Trigger consolidation**: Replace `is_silent`/`is_idle`/`is_callout`/`important_death` flags with two controls: `enable` (checkbox) + `chance` (0–100). `is_important` becomes a local variable, never sent on the wire. **BREAKING**: `flags` dict removed from events. Two new trigger API entry points: `store_event()` (memory only) + `publish_event()` (memory + WS).
- **Memory query resources**: New `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background` resources in `state.query.batch` and `state.mutate.batch`.
- **Remove dead modules**: `SpeakerSelector`, `create_pick_speaker_prompt`, `create_compress_memories_prompt`, `create_update_narrative_prompt`, Lua-side `event_store` (global), `memory.update` WS command, `store.memories` resource, `store.events` resource.

## Capabilities

### New Capabilities
- `four-tier-memory-store`: Per-NPC structured storage with events/summary/digest/core tiers, Background entity, append-only sequential IDs, fan-out from triggers, global event backfill buffer, and unified DSL (append/delete/set/update/query)
- `state-mutate-protocol`: New `state.mutate.batch` WS topic for batched write operations from Python to Lua memory store — supports append, delete, set, update verbs with ID-based addressing
- `tool-based-dialogue`: ConversationManager with single LLM turn using tools (`get_memories`, `background`, `get_character_info`) for inline speaker selection + dialogue generation, replacing the 2-call SpeakerSelector + DialogueGenerator flow
- `compaction-cascade`: Four-tier LLM-driven memory compression (events→summary→digest→core with self-compacting terminal tier), budget-pool batch trigger, atomic delete+append pattern, configurable compaction model

### Modified Capabilities
- `memory-system`: Flat narrative blob → four-tier structured storage; `memory_store` module completely rewritten
- `memory-compression`: Lua-side threshold compression → Python-side compaction cascade via store DSL; all compression logic moves to Python
- `python-dialogue-generator`: 2-call speaker+dialogue flow → single tool-calling ConversationManager turn; `SpeakerSelector` removed
- `python-prompt-builder`: Separate `create_*_prompt()` functions → system prompt + tool definitions; text lookup modules retained for backstory/personality resolution
- `batch-query-protocol`: New `memory.*` resources added to query registry; existing `store.memories`/`store.events` removed
- `ws-api-contract`: New `state.mutate.batch` topic added; `memory.update` command removed; `game.event` payload changes (flags removed, witnesses explicit)
- `lua-event-creation`: `flags` dict removed from events; `Event.create()` signature loses flags parameter; triggers use `store_event`/`publish_event` API
- `talker-persistence`: Save/load rewritten for four-tier memory structure; `event_store` persistence removed; memory_store version migration
- `lua-event-publisher`: `send_game_event()` payload changes — no `is_important` field, witnesses list instead of flags
- `lua-state-query-handler`: New `memory.*` resources registered; mutation handler added for `state.mutate.batch`; old `store.memories`/`store.events` handlers removed

## Impact

- **Lua**: `memory_store.lua` — complete rewrite. `event_store.lua` — removed. `trigger.lua` — new API. All 5 `talker_trigger_*.script` files — updated for new trigger API. `talker_ws_query_handlers.script` — new memory resources + mutation handler. `talker_ws_command_handlers.script` — `memory.update` handler removed. `serializer.lua` — new memory serialization. `talker_game_persistence.script` — new save/load format. `interface.lua` — fan-out logic moved to triggers.
- **Python**: `dialogue/generator.py` — replaced by ConversationManager. `dialogue/speaker.py` — removed. `prompts/dialogue.py`, `prompts/speaker.py`, `prompts/memory.py` — replaced by system prompt + tool schema. `handlers/events.py` — simplified (no `_should_someone_speak`, no speaker selection). `state/client.py` — new mutation methods. `models/messages.py` — new mutation message types. `transport/ws_router.py` — new topic routing.
- **Wire protocol**: `docs/ws-api.yaml` must be updated with `state.mutate.batch` topic, new `memory.*` resources, and changed `game.event` payload.
- **Save compatibility**: Old saves with flat narrative blobs need migration path (load as empty or convert narrative to single core entry).
- **Tests**: ~130 Python tests and ~50 Lua tests need updates or rewrites to match new architecture.
