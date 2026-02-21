# python-state-query-client (delta)

## MODIFIED Requirements

### Requirement: Timeout Handling

The system MUST handle query timeouts with configurable duration. Timeout errors SHALL raise `StateQueryTimeout` (a subclass of `TimeoutError`) to allow callers to distinguish transient connectivity failures from other errors. The `StateQueryTimeout` exception SHALL include the query topic and character_id (if applicable) for diagnostic logging.

#### Scenario: Query times out
- **WHEN** query_memories("123") takes > 30 seconds
- **THEN** `StateQueryTimeout` SHALL be raised (not generic `TimeoutError`)
- **AND** pending request SHALL be cleaned up
- **AND** exception SHALL include topic "state.query.memories" and character_id "123"

#### Scenario: Existing TimeoutError catchers still work
- **WHEN** caller catches `TimeoutError`
- **THEN** `StateQueryTimeout` SHALL be caught (it is a subclass)
- **AND** backward compatibility SHALL be preserved
