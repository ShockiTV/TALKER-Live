## Context

Currently, the memory architecture relies on Lua to filter events and construct the memory context before sending it to Python. `memory_store.lua` fetches new events from `event_store.lua` by comparing timestamps and filtering by the `character_id` in the `witnesses` array. This logic is then exposed via `talker_zmq_query_handlers.script` under the `store.memories` query.

With the introduction of the universal store query language (`filter_engine.lua` and `BatchQuery`), we have the capability to perform complex queries directly from Python. This allows us to move the event filtering logic out of Lua, making `memory_store.lua` a simple key-value store for the narrative and timestamp, and centralizing the complex querying logic in Python.

## Goals / Non-Goals

**Goals:**
- Simplify `memory_store.lua` to only store and retrieve the `narrative` and `last_update_time_ms`.
- Remove event filtering logic (`get_new_events`, `get_memory_context`) from Lua.
- Update `talker_zmq_query_handlers.script` to reflect the simplified `store.memories` response.
- Update Python's `generator.py` to use `BatchQuery` to fetch new events directly from `store.events` using `$elemMatch` on the `witnesses` array.
- Manually construct the `MemoryContext` in Python from the separate `store.memories` and `store.events` query results.

**Non-Goals:**
- Changing the memory compression algorithm or prompts.
- Changing the structure of the `event_store` or `reaction_store`.
- Modifying the ZMQ communication protocol itself.

## Decisions

**Decision 1: Use `$elemMatch` for event filtering in Python**
- **Rationale**: The universal query language supports `$elemMatch` for arrays. We can use this to filter events where the `witnesses` array contains an object with `game_id` equal to the `speaker_id`. This exactly replicates the previous Lua-side filtering logic.
- **Alternative**: Fetch all events since `last_update_time_ms` and filter them in Python. This would be less efficient as it would transfer unnecessary data over ZMQ.

**Decision 2: Simplify `store.memories` response**
- **Rationale**: Since Python will fetch the events directly, `store.memories` only needs to return the `narrative` and `last_update_time_ms`. This makes the Lua side much simpler and aligns with the goal of a "dumb" memory store.
- **Alternative**: Keep `store.memories` returning the full context, but ignore the events in Python. This would be redundant and keep unnecessary complexity in Lua.

## Risks / Trade-offs

- **[Risk]**: The `$elemMatch` query might be slower than the previous Lua-side filtering.
  - **Mitigation**: The `filter_engine.lua` is designed to be efficient, and the `store.events` query handler uses a binary search pre-scan for the `game_time_ms` filter, which should keep performance acceptable. We will monitor performance during testing.
- **[Risk]**: Breaking existing tests that rely on the old `store.memories` response format.
  - **Mitigation**: We will update both Lua and Python tests to reflect the new data flow and response formats.