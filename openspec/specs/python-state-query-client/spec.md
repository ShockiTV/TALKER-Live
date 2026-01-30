# python-state-query-client

## Overview

Python client for requesting state from Lua stores via ZMQ, with timeout handling and response correlation.

## Requirements

### ADDED: State Query Client Class

The system MUST provide `StateQueryClient` class with:
- `async query_memories(character_id, timeout=30) -> MemoryContext`
- `async query_events_recent(since_ms=None, limit=None, timeout=30) -> list[Event]`
- `async query_character(character_id, timeout=30) -> Character`
- `async query_characters_nearby(position, radius, timeout=30) -> list[Character]`

### ADDED: Request-Response Correlation

The system MUST correlate requests and responses by:
- Generating unique request_id (UUID) for each query
- Storing pending requests in dict keyed by request_id
- Matching incoming state.response messages by request_id
- Resolving corresponding asyncio.Future on match

### ADDED: Timeout Handling

The system MUST handle query timeouts by:
- Using asyncio.wait_for with configurable timeout
- Default timeout 30 seconds (from MCM)
- Raising TimeoutError on expiry
- Cleaning up pending request entry on timeout

### ADDED: Response Parsing

The system MUST parse responses by:
- Deserializing JSON payload
- Checking success field
- Returning typed data on success
- Raising QueryError on success=false

### ADDED: Memory Context Model

The system MUST define `MemoryContext` dataclass:
```python
@dataclass
class MemoryContext:
    narrative: str | None
    last_update_time_ms: int
    new_events: list[Event]
```

### ADDED: Graceful Degradation

The system MUST handle failures gracefully:
- Return empty MemoryContext on timeout (not crash)
- Log warnings with request_id
- Allow caller to decide error handling

## Scenarios

#### Query memories successfully

WHEN query_memories("123") is called
THEN request_id is generated
AND state.query is published with type=memories.get
AND client waits for matching state.response
AND MemoryContext is returned with narrative and events

#### Query times out

WHEN query_memories("123") takes > 30 seconds
THEN TimeoutError is raised
AND pending request is cleaned up
AND warning is logged

#### Query returns error

WHEN Lua responds with success=false
THEN QueryError is raised with error message
AND request_id is logged for debugging

#### Concurrent queries

WHEN two queries are made simultaneously
THEN each gets unique request_id
AND responses are correctly correlated
AND neither blocks the other
