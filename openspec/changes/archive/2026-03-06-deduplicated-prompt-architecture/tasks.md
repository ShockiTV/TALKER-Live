## 1. Global Unique Timestamp (Lua)

- [x] 1.1 Create `unique_ts()` function in `bin/lua/domain/service/unique_ts.lua` with `_last_ts` state and collision-bump logic
- [x] 1.2 Wire `unique_ts` into `interface/engine.lua` facade so `bin/lua/` code uses `engine.unique_ts()`
- [x] 1.3 Replace `assign_seq()` calls in `memory_store_v2.lua` with `unique_ts()` — update `store_event`, `fan_out`, `store_global_event`
- [x] 1.4 Remove `next_seq` per-character tracking from `memory_store_v2.lua` init logic
- [x] 1.5 Update `Event.create()` in `domain/model/event.lua` to accept `ts` from `unique_ts()` instead of raw `game_time_ms`
- [x] 1.6 Update `trigger.lua` (`store_event`, `publish_event`) to call `unique_ts()` once and pass to both store and publish
- [x] 1.7 Write Lua tests for `unique_ts()` — same-tick collision, cross-tick normal, reset behavior

## 2. Save/Load Migration v3→v4 (Lua)

- [x] 2.1 Add v3→v4 migration path in `load_save_data()` — replace `seq` fields with `ts`, remove `next_seq`
- [x] 2.2 Update `get_save_data()` to emit `memories_version = "4"`
- [x] 2.3 Update `query()` and `delete()` to use `ts` instead of `seq` for item identity
- [x] 2.4 Write Lua tests for v3→v4 migration — collision handling, field removal, roundtrip

## 3. DeduplicationTracker (Python)

- [x] 3.1 Create `DeduplicationTracker` class in `talker_service/src/talker_service/dialogue/dedup_tracker.py` with three sets and mark/check/rebuild methods
- [x] 3.2 Write unit tests for DeduplicationTracker — mark, check, rebuild_from_messages with tag parsing
- [x] 3.3 Integrate `DeduplicationTracker` into `ConversationManager.__init__()` replacing `_memory_timestamps`

## 4. System Message Injection (Python)

- [x] 4.1 Create helper functions for building tagged system messages: `build_event_system_msg(event)`, `build_bg_system_msg(char_id, name, faction, bg_text)`, `build_mem_system_msg(char_id, start_ts, tier, text)`
- [x] 4.2 Add event system message injection in `handle_event()` — check tracker, inject `EVT:{ts}`, mark
- [x] 4.3 Add background system message injection before picker step — check tracker per candidate, inject `BG:{char_id}`, mark
- [x] 4.4 Add memory system message injection before dialogue step — check tracker per (char_id, start_ts), inject `MEM:{char_id}:{start_ts}`, mark
- [x] 4.5 Wire `rebuild_from_messages()` call after any message pruning
- [x] 4.6 Write tests for system message injection — event dedup, background dedup, memory dedup, rebuild after pruning

## 5. Pointer-Based Picker Messages (Python)

- [x] 5.1 Refactor picker user message to `"Pick speaker for EVT:{ts}. Candidates: {id1}, {id2}, ..."` — remove inline candidate JSON and event description
- [x] 5.2 Update picker cleanup to remove only 2 messages (1 user + 1 assistant) instead of 4
- [x] 5.3 Write tests for lightweight picker message format and cleanup

## 6. Pointer-Based Dialogue Messages (Python)

- [x] 6.1 Refactor dialogue user message to reference `EVT:{ts}`, include character ID and personal narrative only — remove inline event description and background
- [x] 6.2 Handle case where speaker has no personal narrative memories
- [x] 6.3 Write tests for lightweight dialogue message format

## 7. Background Generation Fast Model (Python)

- [x] 7.1 Update `BackgroundGenerator.__init__()` to accept `fast_llm_client` parameter
- [x] 7.2 Update `BackgroundGenerator.generate()` to use `fast_llm_client.complete()`
- [x] 7.3 Update `ConversationManager` (or caller) to pass `fast_llm_client` when constructing `BackgroundGenerator`
- [x] 7.4 Add generated backgrounds as `BG:{char_id}` system messages after generation
- [x] 7.5 Update existing tests for BackgroundGenerator to use fast_llm_client

## 8. Integration & E2E

- [x] 8.1 Run full Python test suite — fix any regressions from conversation message format changes
- [x] 8.2 Run full Lua test suite — fix any regressions from seq→ts migration
- [x] 8.3 Verify e2e scenario tests pass with new system message format
