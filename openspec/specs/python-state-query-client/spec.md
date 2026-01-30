# python-state-query-client

## Purpose

Python client for requesting state from Lua stores via ZMQ, with timeout handling and response correlation.

## Requirements

### State Query Client Class

The system MUST provide `StateQueryClient` class with async query methods.

#### Scenario: Query memories successfully
- **WHEN** query_memories("123") is called
- **THEN** request_id is generated
- **AND** state.query is published with type=memories.get
- **AND** MemoryContext is returned with narrative and events

### Request-Response Correlation

The system MUST correlate requests and responses using unique request_ids.

#### Scenario: Concurrent queries
- **WHEN** two queries are made simultaneously
- **THEN** each gets unique request_id
- **AND** responses are correctly correlated

### Timeout Handling

The system MUST handle query timeouts with configurable duration.

#### Scenario: Query times out
- **WHEN** query_memories("123") takes > 30 seconds
- **THEN** TimeoutError is raised
- **AND** pending request is cleaned up

### Response Parsing

The system MUST parse responses and check success field.

#### Scenario: Query returns error
- **WHEN** Lua responds with success=false
- **THEN** QueryError is raised with error message

### Memory Context Model

The system MUST define `MemoryContext` dataclass with narrative, last_update_time_ms, and new_events.

#### Scenario: MemoryContext creation
- **WHEN** successful query returns memory data
- **THEN** MemoryContext is created with all fields populated

### Graceful Degradation

The system MUST handle failures gracefully without crashing.

#### Scenario: Timeout returns empty context
- **WHEN** query times out
- **THEN** empty MemoryContext is returned
- **AND** warning is logged
