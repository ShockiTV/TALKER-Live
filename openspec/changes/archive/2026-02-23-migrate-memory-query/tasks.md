## 1. Lua Memory Store Simplification

- [x] 1.1 Remove `get_new_events` function from `bin/lua/domain/repo/memory_store.lua`
- [x] 1.2 Remove `get_memory_context` function from `bin/lua/domain/repo/memory_store.lua`
- [x] 1.3 Update `talker_zmq_query_handlers.script` to return only `narrative` and `last_update_time_ms` for `store.memories` queries
- [x] 1.4 Update Lua tests in `tests/repo/test_memory_store.lua` to reflect removed functions
- [x] 1.5 Update Lua tests in `tests/infra/test_zmq_query_handlers.lua` (if any) to reflect the new `store.memories` response format

## 2. Python Dialogue Generator Updates

- [x] 2.1 Update `_generate_dialogue_for_speaker` in `talker_service/src/talker_service/dialogue/generator.py` to add a `store.events` query to the `BatchQuery`
- [x] 2.2 Implement the `$elemMatch` filter for the `store.events` query: `{"witnesses": {"$elemMatch": {"game_id": speaker_id}}}`
- [x] 2.3 Implement the `$gt` filter for the `store.events` query: `{"game_time_ms": {"$gt": last_update_time_ms}}`
- [x] 2.4 Update `_generate_dialogue_for_speaker` to manually construct the `MemoryContext` object using the results from `store.memories` and `store.events`
- [x] 2.5 Update Python tests in `talker_service/tests/dialogue/test_generator.py` to mock the new `BatchQuery` structure and verify `MemoryContext` construction

## 3. Verification and E2E Testing

- [x] 3.1 Run all Lua tests using the `lua-tests` MCP server to ensure no regressions
- [x] 3.2 Run all Python tests using the `talker-tests` MCP server to ensure no regressions
- [x] 3.3 Run Python E2E tests to verify the full dialogue generation flow with the new memory query architecture
