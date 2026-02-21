## Why

Every dialogue generation requires 3–5 sequential ZMQ roundtrips (memories, character, world context, characters alive), each blocked by the Lua game-tick schedule. This adds 200–800ms of pure transport latency before any LLM call. Worse, adding new query types or filter logic requires new Lua handlers paired with new Python methods — making the Lua codebase a maintenance bottleneck. A batch query endpoint with a MongoDB-style filter language lets Python express all data needs in a single request while keeping Lua a generic, stable data-access layer that rarely changes.

## What Changes

- Replace individual `state.query.*` ZMQ topics with a single `state.query.batch` endpoint that accepts an array of sub-queries and returns all results in one response
- Introduce a recursive filter engine in Lua supporting comparison (`$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`), set (`$in`, `$nin`), string (`$regex` with case-insensitive flag), existence (`$exists`), array (`$elemMatch`, `$size`, `$all`), and logical (`$and`, `$or`, `$not`) operators
- Support `sort`, `limit`, and `fields` (projection) on collection resources
- Support `$ref` cross-query value references so later queries in a batch can use values from earlier results (e.g., filtering events by a timestamp retrieved from memories) — Python callers are responsible for correct ordering; no circular dependency detection in Lua
- Introduce `store.*` / `query.*` resource naming convention to distinguish in-memory stores (filterable) from engine pass-through queries (params only, but post-filterable on array results)
- Replace `StateQueryClient` individual query methods with a `BatchQuery` builder and `execute_batch()` method on the Python side
- **BREAKING**: Existing `state.query.memories`, `state.query.character`, `state.query.events`, `state.query.characters_nearby`, `state.query.characters_alive`, `state.query.world` topics will be removed in favour of `state.query.batch`

## Capabilities

### New Capabilities
- `lua-query-filter-engine`: Generic recursive filter evaluator for Lua tables — supports comparison, set, string, existence, array, and logical operators plus sort/limit/projection
- `batch-query-protocol`: Wire protocol for `state.query.batch` — request schema, response schema with per-query error isolation, `$ref` cross-query references, and `store.*`/`query.*` resource naming
- `python-batch-query-client`: Python `BatchQuery` builder and `execute_batch()` on `StateQueryClient` — typed result access, `$ref` helper

### Modified Capabilities
- `lua-state-query-handler`: Existing individual handlers replaced by a single batch dispatcher with resource registry; filter engine applied to store/collection resources
- `python-state-query-client`: Individual `query_*` methods replaced by batch execution; `StateQueryTimeout` semantics preserved but apply to the batch as a whole
- `zmq-api-contract`: `state.query.*` topics removed, `state.query.batch` and `state.response` topics added with new payload schemas

## Impact

- **Lua** (`gamedata/scripts/talker_zmq_query_handlers.script`): Full rewrite — existing per-topic handlers replaced by batch dispatcher + resource registry. New file for filter engine (pure Lua, no game deps).
- **Lua** (`bin/lua/`): New module `infra/query/filter_engine.lua` (~270 lines) — the generic filter evaluator.
- **Python** (`talker_service/src/talker_service/state/client.py`): `StateQueryClient` gains `execute_batch()`; existing `query_*` methods deprecated then removed.
- **Python** (`talker_service/src/talker_service/state/`): New `batch.py` module with `BatchQuery` builder.
- **Python** (`talker_service/src/talker_service/dialogue/generator.py`): Refactored to use single batch call instead of sequential queries.
- **Python** (`talker_service/src/talker_service/prompts/world_context.py`): Characters-alive query uses batch.
- **Wire protocol** (`docs/zmq-api.yaml`): New `state.query.batch` topic replaces 6 individual `state.query.*` topics.
- **Tests**: Lua filter engine tests (offline, pure Lua). Python batch client tests. E2E batch query scenarios.
