# python-batch-query-client

## Purpose

Python `BatchQuery` builder and `execute_batch()` method on `StateQueryClient` for composing and executing batch queries against the Lua state layer in a single ZMQ roundtrip.

## Requirements

### Requirement: BatchQuery builder class

The system SHALL provide a `BatchQuery` class for composing batch query requests. The builder SHALL support chaining `add()` calls and provide a `ref()` helper for generating `$ref` strings.

#### Scenario: Add sub-queries to batch
- **WHEN** `batch.add("mem", "store.memories", params={"character_id": "123"})` is called
- **THEN** the batch SHALL contain one sub-query with id="mem", resource="store.memories", and the given params

#### Scenario: Add sub-query with filter, sort, limit, fields
- **WHEN** `batch.add("ev", "store.events", filter={"type": "death"}, sort={"game_time_ms": -1}, limit=5, fields=["type", "game_time_ms"])` is called
- **THEN** the sub-query SHALL include all specified options in the serialized payload

#### Scenario: ref() helper generates $ref string
- **WHEN** `batch.ref("mem", "last_update_time_ms")` is called
- **THEN** it SHALL return the string `"$ref:mem.last_update_time_ms"`

#### Scenario: Builder is chainable
- **WHEN** `batch.add(...).add(...).add(...)` is called
- **THEN** each `add()` SHALL return the `BatchQuery` instance for chaining

### Requirement: execute_batch on StateQueryClient

The `StateQueryClient` SHALL provide an `async execute_batch(batch: BatchQuery) -> BatchResult` method that sends the batch request via ZMQ and returns results.

#### Scenario: Execute batch with single roundtrip
- **WHEN** `execute_batch(batch)` is called with a batch containing 4 sub-queries
- **THEN** exactly one ZMQ message SHALL be published on topic `state.query.batch`
- **AND** exactly one response SHALL be awaited on `state.response`

#### Scenario: Timeout on batch
- **WHEN** `execute_batch(batch)` takes longer than the configured timeout
- **THEN** `StateQueryTimeout` SHALL be raised
- **AND** the exception SHALL include topic `"state.query.batch"`

### Requirement: BatchResult accessor

The `execute_batch()` return value SHALL provide typed access to individual sub-query results by their `id`.

#### Scenario: Access successful result by id
- **WHEN** `result["mem"]` is accessed and sub-query "mem" succeeded
- **THEN** it SHALL return the deserialized `data` value

#### Scenario: Access failed result by id
- **WHEN** `result["mem"]` is accessed and sub-query "mem" failed
- **THEN** it SHALL raise `QueryError` with the error message from the response

#### Scenario: Check if sub-query succeeded
- **WHEN** `result.ok("mem")` is called
- **THEN** it SHALL return `True` if sub-query "mem" has `ok: true`, `False` otherwise

#### Scenario: Access non-existent id
- **WHEN** `result["nonexistent"]` is accessed
- **THEN** it SHALL raise `KeyError`

### Requirement: Query ordering validation

The `BatchQuery` builder SHOULD validate at build time that `$ref` references only point to sub-query IDs declared earlier in the add order. If validation fails, a `ValueError` SHALL be raised before sending.

#### Scenario: Valid $ref ordering
- **WHEN** batch has queries ["mem", "ev"] and "ev" references "$ref:mem.x"
- **THEN** validation SHALL pass (mem is declared before ev)

#### Scenario: Invalid $ref ordering detected
- **WHEN** batch has queries ["ev", "mem"] and "ev" references "$ref:mem.x"
- **THEN** `ValueError` SHALL be raised with message indicating "mem" is not yet declared

#### Scenario: $ref to undeclared query
- **WHEN** batch references "$ref:missing.x" and no query with id "missing" exists
- **THEN** `ValueError` SHALL be raised with message indicating "missing" is not a known query id
