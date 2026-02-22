## Why

The current memory architecture relies on Lua to filter events and construct the memory context before sending it to Python. With the introduction of the universal store query language (`filter_engine.lua` and `BatchQuery`), we can move this logic entirely to Python. This simplifies the Lua `memory_store` to just hold the narrative and timestamp, making it a "dumb" store and centralizing the complex querying and filtering logic in Python.

## What Changes

- Modify `talker_service/src/talker_service/dialogue/generator.py` to use the universal query language to fetch new events directly from `store.events` using `$elemMatch` on the `witnesses` array.
- Remove event filtering logic (`get_new_events`, `get_memory_context`) from Lua's `memory_store.lua`.
- Update Lua's `talker_zmq_query_handlers.script` so that `store.memories` only returns the `narrative` and `last_update_time_ms` from `memory_store.lua`.
- Update Python's `generator.py` to manually construct the `MemoryContext` from the separate `store.memories` and `store.events` query results.

## Capabilities

### New Capabilities
- `memory-query-migration`: Migrating the memory context construction to use the universal store query language from Python.

### Modified Capabilities
- `memory-system`: The way memory context is fetched and constructed is changing from Lua-side filtering to Python-side querying.

## Impact

- **Lua**: `memory_store.lua` becomes simpler. `talker_zmq_query_handlers.script` is updated to reflect the simpler `store.memories` response.
- **Python**: `generator.py` batch query is updated to fetch events directly and construct the `MemoryContext`.
- **Tests**: Lua and Python tests related to memory fetching and batch queries will need to be updated to reflect the new data flow.