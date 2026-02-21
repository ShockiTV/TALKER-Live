## Context

The Python service currently makes 3–5 sequential ZMQ roundtrips per dialogue generation to fetch memories, character data, world context, and alive-status from Lua. Each roundtrip is gated by the Lua game-tick poll cycle, adding 200–800ms of transport latency before any LLM call begins. Adding new query types or filter capabilities requires paired changes in both Lua handlers and Python client methods, making Lua a maintenance bottleneck.

The system uses ZMQ PUB/SUB with request-ID correlation: Python publishes a query, Lua handles it on the next game tick, and publishes a response. This mechanism is retained — only the payload schema changes.

## Goals / Non-Goals

**Goals:**
- Reduce state-fetching roundtrips from N to 1 per dialogue generation
- Provide a generic filter/sort/limit/project query language on the Lua side so Python can express new data access patterns without Lua code changes
- Establish a stable, testable Lua data-access layer (~270 lines) that rarely needs modification
- Support cross-query value references (`$ref`) for single-batch joins (e.g., "events since this character's last memory update")
- Distinguish store resources (in-memory, filterable) from engine query resources (pass-through) via naming convention

**Non-Goals:**
- Aggregation pipeline (GROUP BY, COUNT, SUM) — data volumes are too small to justify
- Client-side caching / CQRS event-sourced state — adds complexity without proportional benefit at current scale
- GraphQL or JSON-RPC specification compliance — custom protocol is simpler and sufficient
- Lua-side circular dependency detection for `$ref` — Python callers are responsible for correct query ordering

## Decisions

### 1. MongoDB-style filter language over GraphQL or JSON-RPC

**Decision**: Use a MongoDB-inspired filter document syntax (`$eq`, `$gt`, `$in`, `$and`, `$or`, `$elemMatch`, etc.) evaluated recursively in Lua.

**Alternatives considered**:
- **GraphQL (Strawberry in Python)**: Powerful schema/introspection, but requires a Python GraphQL runtime adding dependency complexity. The batch-with-filters approach gives equivalent data-fetching capability with simpler infrastructure.
- **JSON-RPC 2.0 Batch**: Good wire protocol, but lacks a filter language — would still need custom filter semantics on top.
- **DataLoader pattern (Python-only)**: Parallelizes existing calls but doesn't reduce roundtrips without Lua-side batch support.

**Rationale**: The filter syntax is well-understood (MongoDB precedent), requires ~270 lines of pure Lua, handles recursive composition naturally, and puts all query-composition intelligence in Python.

### 2. Single `state.query.batch` topic replacing individual `state.query.*` topics

**Decision**: One ZMQ topic (`state.query.batch`) accepts an array of sub-queries. Each sub-query has an `id`, `resource`, optional `params`, `filter`, `sort`, `limit`, `fields`. Response returns per-query results keyed by `id` with `ok`/`error` isolation.

**Rationale**: Reduces roundtrips to exactly 1. Per-query error isolation means a failed sub-query doesn't abort the entire batch. The `id` field allows Python to name results for readable access.

### 3. `store.*` / `query.*` resource naming convention

**Decision**: Resource names use a `<type>.<name>` convention:
- `store.*` — In-memory Lua tables (event_store, memory_store). Filter engine applies.
- `query.*` — Engine API pass-through (character lookup, world context, alive checks). Params-driven, but post-filtering supported on array results.

**Rationale**: The prefix communicates capability at a glance. Python developers know `store.events` supports arbitrary filters while `query.character` is a keyed lookup. No extra metadata field needed.

**Resource registry**:

| Resource | Type | Source | Filterable |
|----------|------|--------|------------|
| `store.events` | store | event_store | Yes (collection) |
| `store.memories` | store | memory_store | No (single document by character_id) |
| `store.personalities` | store | personalities repo | Yes (collection of {character_id, personality_id}) |
| `store.backstories` | store | backstories repo | Yes (collection of {character_id, backstory_id}) |
| `store.levels` | store | levels repo | Yes (collection of {level_id, count, log[]}) |
| `store.timers` | store | timers repo | No (singleton: game_time_accumulator, idle_last_check_time) |
| `query.character` | query | game_adapter.get_character_by_id | No (by ID) |
| `query.characters_nearby` | query | game_adapter.get_characters_near | Yes (post-filter on array result) |
| `query.characters_alive` | query | alife() story object checks | No (by IDs) |
| `query.world` | query | talker_game_queries | No (singleton) |

### 4. `$ref` cross-query references with ordered execution

**Decision**: String values starting with `"$ref:<query_id>.<dotted.path>"` are resolved against earlier query results. Queries execute sequentially in array order. A `$ref` to an unresolved or failed query produces a per-query error.

**Rationale**: Enables the critical `memories → events` join pattern (filter events by character's last memory update timestamp) in a single batch. No cycle detection in Lua — Python is responsible for topological ordering. The `$ref` resolver is ~25 lines.

### 5. Recursive filter evaluator with full operator set

**Decision**: The filter engine supports:

| Category | Operators |
|----------|-----------|
| Comparison | `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte` |
| Set | `$in`, `$nin` |
| String | `$regex` (Lua patterns), `$regex_flags` (`"i"` for case-insensitive) |
| Existence | `$exists` |
| Array | `$elemMatch`, `$size`, `$all` |
| Logical | `$and`, `$or`, `$not` |

Top-level filter keys are implicitly ANDed. `$and`, `$or`, `$not`, and `$elemMatch` recurse back into `evaluate_filter`, making the evaluator a single recursive function.

**`$regex` note**: Uses Lua patterns (not PCRE). No alternation support — use `$in` for exact alternation or `$or` with multiple `$regex` for pattern alternation. Case-insensitive flag lowercases both sides before matching.

### 6. Field projection defaults to full documents

**Decision**: When `fields` array is absent, return the complete document. When present, extract only the listed dotted paths and build a nested result structure. Projection applies per-element on collection results.

**Rationale**: Keeps the common case simple (no fields = everything). Projection is available for bandwidth-sensitive queries. Implementation is ~20 lines of Lua.

### 7. Filter engine lives in `bin/lua/infra/query/` — no game dependencies

**Decision**: The filter engine module (`filter_engine.lua`) is pure Lua with zero game API calls. It takes a document (table) and a filter document (table) and returns a boolean. The pipeline orchestrator and projection are separate pure functions in the same module.

**Rationale**: Testable offline with `lua5.1.exe`. Follows the project's clean architecture (infra layer, no game deps). The batch handler in `gamedata/scripts/` imports it and applies it to resource results.

### 8. Fused pipeline strategies to minimize memory footprint

**Decision**: Instead of four sequential stages (filter → sort → limit → project) that materialize intermediate arrays, the pipeline orchestrator selects a strategy based on which stages are present:

| Stages present | Strategy | Peak memory |
|---|---|---|
| sort + limit | **Fused top-N scan**: single pass maintaining a bounded sorted buffer of `limit` refs | O(limit) |
| limit only | **Early-termination scan**: stop after `limit` matches | O(limit) |
| sort only | **Sort-then-hydrate**: sort `{key, sort_val}` pairs, hydrate at end | O(N) sort-key pairs, not full docs |
| filter only (no sort, no limit) | **Streaming filter**: collect matching refs | O(matches) |

The fused top-N strategy works by scanning the source, evaluating the filter, and inserting into a bounded sorted buffer (binary insertion into an array of size `limit`). When the buffer is full, a new match replaces the worst element only if it compares better. This avoids materializing all filtered results.

Projection applies last, only to the final result set. Serialization (the actual memory cost) only touches the limited+projected set.

**Source iterators**: Collection resources provide an **iterator function** instead of a full array. This enables the event_store to supply a pre-narrowed iterator starting from a binary-search position on `sorted_keys` when a `game_time_ms` range filter is detected, skipping old events entirely.

**Alternatives considered**:
- **Filter-then-sort-then-limit (naive pipeline)**: Simple but materializes all filtered results before limiting. With 800 matches and limit=12, holds 800 refs through sort before discarding 788. Reported to cause memory pressure on the previous solution.
- **Heap-based top-N**: O(N log limit) vs O(N × limit) for binary insertion. For limit ≤ 20 (typical), binary insertion into a small array is fewer comparisons and no heap overhead.

**Rationale**: The typical dialogue query has sort + limit (e.g., "12 most recent death events witnessed by X"). The fused top-N scan keeps peak refs at 12 regardless of store size. The iterator interface lets event_store skip irrelevant time ranges without the pipeline knowing about the index.

## Risks / Trade-offs

**Risk: `$regex` with Lua patterns may confuse Python developers expecting PCRE**
→ Mitigation: Document clearly in zmq-api.yaml that `$regex` uses Lua patterns. The Python `BatchQuery` builder can include a docstring warning. Most common patterns (anchors, character classes, repetition) work identically. Alternation (missing from Lua patterns) is handled by `$in` or `$or`.

**Risk: `$ref` ordering errors produce confusing failures**
→ Mitigation: Clear per-query error messages (`"$ref: 'mem' not yet resolved"`). Python `BatchQuery` builder can validate ordering at build time before sending.

**Risk: Large event stores may make unindexed `$elemMatch` on witnesses slow**
→ Mitigation: event_store typically holds hundreds of events, not thousands. The iterator interface lets event_store binary-search `sorted_keys` to start scanning from the time-range boundary, drastically reducing the scan set before `$elemMatch` runs. The fused top-N pipeline then caps memory at O(limit). If needed later, Lua can add a witness index — no wire protocol change required.

**Risk: Memory pressure from materializing intermediate filter results**
→ Mitigation: The fused pipeline strategies (Decision 8) avoid materializing intermediate arrays. The top-N scan holds at most `limit` references during the scan. Source iterators avoid copying the store. Projection and serialization apply only to the final bounded result set.

**Risk: Breaking change removes all existing `state.query.*` topics**
→ Mitigation: Implement batch endpoint first, migrate Python callers one-by-one, remove old handlers last. Transition can be staged across multiple commits.

## Migration Plan

1. **Phase 1 — Lua filter engine**: Create `bin/lua/infra/query/filter_engine.lua` with full operator set. Add Lua unit tests. No game integration yet.
2. **Phase 2 — Lua batch handler**: Create batch query dispatcher in `talker_zmq_query_handlers.script` alongside existing handlers. Register `state.query.batch` topic. Existing `state.query.*` handlers remain operational.
3. **Phase 3 — Python batch client**: Create `BatchQuery` builder and `execute_batch()` on `StateQueryClient`. Add Python unit tests.
4. **Phase 4 — Migrate callers**: Update `DialogueGenerator`, `SpeakerSelector`, `world_context.py` to use batch queries. Verify with E2E tests.
5. **Phase 5 — Cleanup**: Remove old `state.query.*` handlers from Lua and old `query_*` methods from Python `StateQueryClient`. Update `zmq-api.yaml`.

**Rollback**: Each phase is independently deployable. If batch handler has issues, old handlers still work. Python callers can be reverted to individual queries without Lua changes.

## Open Questions

- Should `store.memories` support `$ref` in its `params.character_id` (e.g., `"$ref:char.game_id"`)? Currently `$ref` only resolves inside `filter`. Extending it to `params` adds ~5 lines of Lua but enables more composition.
