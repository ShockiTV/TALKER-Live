## 1. Lua: Four-Tier Memory Store (Core Data Layer)

- [ ] 1.1 Create `bin/lua/domain/repo/memory_store_v2.lua` with per-NPC storage structure (events, summaries, digests, cores, background tiers), sequential IDs, and tier capacity constants
- [ ] 1.2 Implement `memory_store:store_event(character_id, event)` — assigns seq, appends to character's events tier, enforces 100-event cap (oldest evicted)
- [ ] 1.3 Implement `memory_store:fan_out(event, witnesses)` — stores event copy in each witness NPC's events tier
- [ ] 1.4 Implement `memory_store:query(character_id, resource, params)` DSL — resolves `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`; supports `from_timestamp` filter on events
- [ ] 1.5 Implement `memory_store:mutate(character_id, verb, resource, data)` DSL — supports `append`, `delete` (by seq_lte), `set`, `update` verbs across all tiers
- [ ] 1.6 Implement `memory_store:save()` and `memory_store:load()` with v3 format; include v2→v3 migration (narrative → cores[0]) and v1→v2→v3 chain
- [ ] 1.7 Write Lua tests for memory_store_v2: store_event, fan_out, query DSL, mutate DSL, capacity enforcement, save/load, v2→v3 migration

## 2. Lua: State Mutation Handler (WS Layer)

- [ ] 2.1 Add `state.mutate.batch` topic handler in `talker_ws_query_handlers.script` — parse mutations array, dispatch each to `memory_store:mutate()`, collect results, respond with `state.response`
- [ ] 2.2 Register `memory.*` resources in the query handler resource registry — delegate to `memory_store:query()`
- [ ] 2.3 Remove `store.events` and `store.memories` from the resource registry; remove old `memory.update` command handler from `talker_ws_command_handlers.script`
- [ ] 2.4 Write Lua tests for mutation handler: append, delete, mixed success/failure, unknown resource

## 3. Lua: Trigger Consolidation (DEATH Skeleton)

- [ ] 3.1 Create `trigger.store_and_publish(event_type, context, witnesses)` in `bin/lua/interface/trigger.lua` — creates event, stores in speaker's memory, fans out to witnesses, publishes over WS with candidates + world + traits
- [ ] 3.2 Build traits map helper: for each candidate, look up `{personality_id, backstory_id}` from personality/backstory repos
- [ ] 3.3 Refactor `talker_trigger_death.script` to use `trigger.store_and_publish()` instead of `trigger.talker_event_near_player()`; remove flags/is_important
- [ ] 3.4 Update `send_game_event` in `bin/lua/infra/ws/publisher.lua` to accept `(event, candidates, world, traits)` — drop `is_important` parameter
- [ ] 3.5 Update serializer to serialize new payload shape: `{event, candidates, world, traits}`

## 4. Python: ConversationManager (Tool-Based Dialogue)

- [ ] 4.1 Create `talker_service/src/talker_service/dialogue/conversation.py` with `ConversationManager` class — holds `StateQueryClient` and `LLMClient` refs
- [ ] 4.2 Implement system prompt builder: faction, personality, world context, tool usage instructions
- [ ] 4.3 Implement event message builder: format event + candidates list + traits summary into user message
- [ ] 4.4 Define tool schemas: `get_memories(character_id, tiers)` and `get_background(character_id)`; implement tool dispatch via `StateQueryClient` batch queries
- [ ] 4.5 Implement tool loop: send messages to LLM, detect tool_calls, execute tools, append results, re-call LLM until text response; extract speaker + dialogue from final response
- [ ] 4.6 Implement pre-fetch optimization: batch query for event character's memories before first LLM call to seed context
- [ ] 4.7 Write Python tests for ConversationManager: system prompt assembly, tool dispatch, tool loop with mocked LLM, response extraction

## 5. Python: Event Handler Rewire

- [ ] 5.1 Update `handlers/events.py` to parse new `game.event` payload shape (`{event, candidates, world, traits}` — no `is_important`)
- [ ] 5.2 Replace `DialogueGenerator` + `SpeakerSelector` call chain with single `ConversationManager.handle_event()` call
- [ ] 5.3 Remove old `handlers/events.py` speaker selection logic and `dialogue/speaker.py` module
- [ ] 5.4 Update `player.dialogue` and `player.whisper` handlers to use ConversationManager
- [ ] 5.5 Write Python tests for updated event handler: payload parsing, ConversationManager integration

## 6. Python: Compaction Cascade

- [ ] 6.1 Create `talker_service/src/talker_service/memory/compaction.py` with `CompactionEngine` class — accepts `StateQueryClient` and `LLMClient`
- [ ] 6.2 Implement tier-specific compaction: events→summaries (summarize N events into 1 summary), summaries→digests, digests→cores
- [ ] 6.3 Implement atomic compaction pattern: query source tier, call LLM to compress, send `state.mutate.batch` with delete(source, seq_lte) + append(target, compressed)
- [ ] 6.4 Implement budget-pool trigger: after tool loop completes, check all characters that received events; if any tier exceeds threshold, schedule compaction
- [ ] 6.5 Implement non-blocking compaction: use `asyncio.create_task()` so compaction doesn't block the dialogue response
- [ ] 6.6 Create compaction prompts in `talker_service/src/talker_service/prompts/compaction.py`
- [ ] 6.7 Write Python tests for CompactionEngine: tier transitions, atomic pattern, threshold logic, LLM prompt construction

## 7. Widen: All Event Types + Triggers

- [ ] 7.1 Refactor remaining triggers to use `trigger.store_and_publish()`: injury, artifact, anomaly, emission, map_transition, idle, weapon_jam, reload, sleep, task, callout, taunt, action
- [ ] 7.2 Remove `domain/service/importance.lua` and all references to importance flags across trigger scripts
- [ ] 7.3 Remove global `event_store` repo: delete `bin/lua/domain/repo/event_store.lua`, remove from persistence hooks, remove `talker_game_files.load_event_store`/`save_event_store`
- [ ] 7.4 Update `talker.lua` app orchestrator to use new memory_store_v2 instead of old event_store + memory_store

## 8. Python: Cleanup Old Modules

- [ ] 8.1 Remove `dialogue/speaker.py` (SpeakerSelector), `dialogue/generator.py` (DialogueGenerator)
- [ ] 8.2 Remove old prompt builders: `prompts/dialogue.py`, `prompts/speaker.py`, `prompts/memory.py` and related helpers
- [ ] 8.3 Remove `prompts/builder.py`, `prompts/helpers.py`, `prompts/models.py` if no longer referenced
- [ ] 8.4 Update `prompts/lookup.py` to add `resolve_location_name()` if needed by ConversationManager
- [ ] 8.5 Remove `state/models.py` old query models if replaced

## 9. Wire Protocol + Integration

- [ ] 9.1 Update `docs/ws-api.yaml` to reflect new topics (`state.mutate.batch`), removed topics (`memory.update`), and updated `game.event` payload
- [ ] 9.2 Update Pydantic message schemas in `talker_service/src/talker_service/models/messages.py` for new payload shapes
- [ ] 9.3 Run full Lua test suite — fix any regressions from memory_store, trigger, and serializer changes
- [ ] 9.4 Run full Python test suite — fix any regressions from handler, dialogue, and prompt changes
- [ ] 9.5 End-to-end manual test: start service, load game, trigger DEATH event, verify tool-based dialogue flows through all layers
