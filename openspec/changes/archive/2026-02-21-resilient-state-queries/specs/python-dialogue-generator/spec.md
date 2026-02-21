# python-dialogue-generator (delta)

## MODIFIED Requirements

### Requirement: Error Handling

The system MUST handle errors with distinction between transient and permanent failures:
- `StateQueryTimeout` errors (transient): SHALL defer the request to the retry queue if one is configured, instead of discarding
- LLM errors, `ConnectionError`, data errors (permanent): SHALL be caught, logged, and discarded as before
- If no retry queue is configured (None), timeout failures SHALL be handled as before (logged and discarded) for backward compatibility

#### Scenario: State query timeout deferred to retry queue
- **WHEN** `_generate_dialogue_for_speaker()` raises `StateQueryTimeout`
- **AND** a retry queue is configured
- **THEN** the event SHALL be enqueued to the retry queue
- **AND** a warning SHALL be logged indicating deferral
- **AND** no dialogue.display command SHALL be sent

#### Scenario: State query timeout without retry queue (backward compat)
- **WHEN** `_generate_dialogue_for_speaker()` raises `StateQueryTimeout`
- **AND** no retry queue is configured (None)
- **THEN** error SHALL be logged
- **AND** no dialogue.display command SHALL be sent
- **AND** behavior SHALL match current implementation

#### Scenario: LLM timeout handled as permanent failure
- **WHEN** LLM call exceeds timeout
- **THEN** error SHALL be caught and logged
- **AND** request SHALL NOT be enqueued to retry queue
- **AND** no dialogue.display command SHALL be sent

### Requirement: Retry queue injection

The `DialogueGenerator` constructor SHALL accept an optional `retry_queue` parameter (default None). When provided, the generator SHALL use it to defer transient failures. When None, behavior SHALL be identical to the current implementation.

#### Scenario: Generator created with retry queue
- **WHEN** `DialogueGenerator(llm_client, state_client, publisher, retry_queue=queue)` is called
- **THEN** the generator SHALL use the provided queue for deferral

#### Scenario: Generator created without retry queue
- **WHEN** `DialogueGenerator(llm_client, state_client, publisher)` is called
- **THEN** the generator SHALL handle all errors as before (log and discard)
