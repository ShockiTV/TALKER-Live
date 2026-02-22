## MODIFIED Requirements

### Requirement: Memory Store Responsibilities
The Lua `memory_store` SHALL only be responsible for storing and retrieving the `narrative` and `last_update_time_ms` for a character. It SHALL NOT filter or construct the full `MemoryContext`.

#### Scenario: Retrieving memory context from Lua
- **WHEN** the Python service queries `store.memories` for a character
- **THEN** the Lua `memory_store` SHALL return only the `narrative` and `last_update_time_ms`
- **THEN** the Lua `memory_store` SHALL NOT return the `new_events` array

## REMOVED Requirements

### Requirement: Lua-side Event Filtering
**Reason**: The universal store query language allows Python to query events directly, making Lua-side filtering redundant and complex.
**Migration**: Use the `$elemMatch` operator in Python's `BatchQuery` to filter `store.events` by witness. Remove `get_new_events` and `get_memory_context` from `memory_store.lua`.
