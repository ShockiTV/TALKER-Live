## 1. Lua Filter Engine (Pure Lua, No Game Deps)

- [x] 1.1 Create `bin/lua/infra/query/filter_engine.lua` module skeleton with `evaluate_filter`, `execute_pipeline`, `apply_projection` exports
- [x] 1.2 Implement dotted field path resolver (`resolve_path`) with numeric index mapping (0-based wire → 1-based Lua)
- [x] 1.3 Implement comparison operators ($eq, $ne, $gt, $gte, $lt, $lte) with implicit $eq shorthand for bare values
- [x] 1.4 Implement set operators ($in, $nin)
- [x] 1.5 Implement string operator ($regex with Lua patterns, $regex_flags "i" for case-insensitive)
- [x] 1.6 Implement existence operator ($exists true/false)
- [x] 1.7 Implement array operators ($elemMatch, $size, $all) — $elemMatch recurses into evaluate_filter
- [x] 1.8 Implement logical operators ($and, $or, $not) — recurse into evaluate_filter; top-level keys implicitly ANDed
- [x] 1.9 Implement `execute_pipeline(source_iter, filter, sort, limit)` — strategy selector: fused top-N (sort+limit), early-termination (limit only), sort-all (sort only), collect-all (filter only)
- [x] 1.10 Implement fused top-N scan — bounded sorted buffer with binary insertion, O(limit) peak memory
- [x] 1.11 Implement early-termination scan — stop after `limit` filter matches
- [x] 1.12 Implement `apply_projection(doc, fields)` — extract dotted paths into nested result structure
- [x] 1.13 Implement `$ref` resolver function — recursively walk a table replacing `"$ref:..."` strings with resolved values from a results map
- [x] 1.14 Create Lua unit tests (`tests/infra/query/test_filter_engine.lua`) covering all operators, pipeline strategies, edge cases (nil fields, empty arrays, nested paths)

## 2. Lua Batch Query Handler

- [x] 2.1 Create resource registry table in `talker_zmq_query_handlers.script` mapping resource names to resolver functions
- [x] 2.2 Implement `store.events` resolver — provides iterator over event_store (with binary-search pre-scan on `sorted_keys` when `game_time_ms` range filter detected), feeds into `execute_pipeline`, applies projection to final result
- [x] 2.3 Implement `store.memories` resolver — calls `memory_store:get_memory_context(character_id)`, requires `params.character_id`, returns single document
- [x] 2.4 Implement `store.personalities` resolver — iterates personalities repo `character_personalities` map, returns array of `{character_id, personality_id}`, applies filter pipeline
- [x] 2.5 Implement `store.backstories` resolver — iterates backstories repo `character_backstories` map, returns array of `{character_id, backstory_id}`, applies filter pipeline
- [x] 2.6 Implement `store.levels` resolver — iterates levels repo `visits` map, returns array of `{level_id, count, log}`, supports `params.level_id` for single lookup, applies filter pipeline
- [x] 2.7 Implement `store.timers` resolver — returns singleton `{game_time_accumulator, idle_last_check_time}` from timers repo
- [x] 2.8 Implement `query.character` resolver — calls `game_adapter.get_character_by_id(id)`, requires `params.id`, returns single document
- [x] 2.9 Implement `query.characters_nearby` resolver — calls `game_adapter.get_characters_near()`, returns array, supports post-filter
- [x] 2.10 Implement `query.characters_alive` resolver — calls alife() story object checks, requires `params.ids`, returns id→boolean map
- [x] 2.11 Implement `query.world` resolver — calls existing world context builder, returns singleton object
- [x] 2.12 Implement batch dispatcher: register `state.query.batch` topic handler, iterate queries in order, dispatch to registry, collect results with per-query error isolation via pcall
- [x] 2.13 Implement `$ref` resolution pass: before each sub-query executes, resolve `$ref` strings in its `filter` and `params` using the ref resolver from 1.12 against accumulated results
- [x] 2.14 Wire `execute_pipeline` into store resolvers — each store resolver creates a source iterator and calls `filter_engine.execute_pipeline(iter, filter, sort, limit)`, then applies projection to the result
- [x] 2.15 Create Lua integration test for batch handler with mock stores (verify dispatch, $ref resolution, error isolation)

## 3. Python Batch Query Client

- [x] 3.1 Create `BatchQuery` builder class in `talker_service/src/talker_service/state/batch.py` with `add()` chaining and `ref()` helper
- [x] 3.2 Implement `$ref` ordering validation in `BatchQuery.build()` — raise `ValueError` if a $ref references a query ID not yet declared
- [x] 3.3 Create `BatchResult` accessor class with `__getitem__` (returns data or raises `QueryError`), `ok(id)` method, and `KeyError` for unknown IDs
- [x] 3.4 Create `QueryError` exception in state module
- [x] 3.5 Add `execute_batch(batch: BatchQuery) -> BatchResult` method to `StateQueryClient` — publishes single ZMQ message on `state.query.batch`, awaits correlated `state.response`
- [x] 3.6 Add Pydantic models for batch request/response in `talker_service/src/talker_service/models/messages.py`
- [x] 3.7 Write Python unit tests for `BatchQuery` builder (add, ref, ordering validation, build output)
- [x] 3.8 Write Python unit tests for `BatchResult` accessor (success, error, missing key)
- [x] 3.9 Write Python unit tests for `execute_batch` (mock ZMQ, timeout handling, response correlation)

## 4. Migrate Python Callers to Batch Queries

- [x] 4.1 Add deprecation warnings to existing `query_*` methods on `StateQueryClient` (query_memories, query_character, query_world_context, query_characters_nearby, query_events_recent)
- [x] 4.2 Migrate `DialogueGenerator._generate_dialogue_for_speaker()` to use single `execute_batch()` call replacing sequential query_memories → query_character → query_world_context calls
- [x] 4.3 Migrate `SpeakerSelector` to use batch queries if it fetches state
- [x] 4.4 Migrate `world_context.py` / `build_world_context()` to use batch queries (query_characters_alive is called from here)
- [x] 4.5 Migrate any remaining callers of individual `query_*` methods
- [x] 4.6 Update existing Python tests to work with batch-based callers (mock execute_batch instead of individual query methods)
- [x] 4.7 Run full E2E test suite to verify batch-based dialogue generation works end-to-end

## 5. Cleanup and Documentation

- [x] 5.1 Remove individual `state.query.*` topic handlers from `talker_zmq_query_handlers.script` (memories, events, character, characters_nearby, characters_alive, world)
- [x] 5.2 Remove deprecated `query_*` methods from `StateQueryClient`
- [x] 5.3 Update `docs/zmq-api.yaml` — add `state.query.batch` definition with FilterDocument type and resource registry; remove individual `state.query.*` entries
- [x] 5.4 Update `AGENTS.md` ZMQ topics table and state query documentation
- [x] 5.5 Remove old `state.query.*` subscription handling from Python `ZMQRouter` if present (confirmed: none existed, router uses generic request_id correlation)
