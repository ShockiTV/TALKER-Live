# python-dialogue-generator

## Purpose

Python orchestrator that handles the full dialogue generation flow: event reception → speaker selection → memory management → prompt building → LLM call → display command. The Python service is the SOLE dialogue generation path - there is no Lua fallback.

## Requirements

### Dialogue Generator Service

The system MUST provide `DialogueGenerator` class as the sole dialogue generation path. There SHALL be no alternative or fallback dialogue generation mechanism.

The `DialogueGenerator` class MUST provide:
- `async generate(event, is_important)` method as main entry point
- Access to state query client for fetching Lua state
- Access to LLM client for AI completions
- Access to prompt builder for prompt construction
- Publisher for sending display commands

#### Scenario: All dialogue flows through Python service
- **WHEN** any dialogue-triggering event occurs
- **THEN** dialogue generation SHALL be handled exclusively by the Python DialogueGenerator
- **AND** no Lua-side AI processing SHALL occur

#### Scenario: Service unavailable during dialogue request
- **WHEN** a dialogue request cannot be fulfilled due to service issues
- **THEN** the request SHALL fail gracefully (no dialogue displayed)
- **AND** there SHALL be no fallback to Lua-based generation

### Speaker Selection Flow

The system MUST implement speaker selection that:
- Receives witnesses from event data
- Filters speakers by cooldown (3 second default)
- If single speaker available, selects directly
- If multiple speakers, calls LLM with pick_speaker prompt
- Validates selected speaker ID against witness list
- Sets speaker cooldown after selection

#### Scenario: Single speaker selected directly
- **WHEN** event has only one witness not on cooldown
- **THEN** that speaker SHALL be selected without LLM call
- **AND** speaker cooldown SHALL be set

#### Scenario: Multiple speakers use LLM selection
- **WHEN** event has multiple witnesses not on cooldown
- **THEN** LLM SHALL be called with pick_speaker prompt
- **AND** selected speaker ID SHALL be validated against witness list

### Memory Context Fetching

The system MUST fetch memory context by:
- Sending `memories.get` query to Lua with character_id
- Receiving narrative + new_events in response
- Handling query timeout (30 second default)
- Returning empty context on failure (graceful degradation)

#### Scenario: Memory context fetched successfully
- **WHEN** state query for memories succeeds
- **THEN** narrative and new_events SHALL be returned
- **AND** context SHALL be used for dialogue generation

#### Scenario: Memory query times out
- **WHEN** state query exceeds 30 second timeout
- **THEN** empty context SHALL be returned
- **AND** dialogue generation SHALL continue with degraded context

### Memory Compression Trigger

The system MUST trigger memory compression when:
- New events count exceeds COMPRESSION_THRESHOLD (12)
- Acquires lock to prevent concurrent updates for same character
- Calls LLM with compression/update_narrative prompts
- Sends `memory.update` command to Lua with new narrative
- Releases lock after completion

#### Scenario: Memory compression triggered
- **WHEN** new_events count >= 12 for a character
- **THEN** compression lock SHALL be acquired
- **AND** LLM SHALL generate compressed summary
- **AND** memory.update command SHALL be sent to Lua

### Dialogue Request Flow

The system MUST request dialogue by:
- Building dialogue prompt with speaker + memory context
- Calling LLM for completion
- Cleaning/improving response text
- Sending `dialogue.display` command to Lua

#### Scenario: Dialogue generated and displayed
- **WHEN** dialogue prompt is sent to LLM
- **THEN** response SHALL be cleaned and formatted
- **AND** dialogue.display command SHALL be sent to Lua

### Request-Response Correlation

The system MUST use correlation IDs:
- Generate unique request_id for each dialogue flow
- Include request_id in all queries and commands
- Track in-flight requests for timeout handling
- Log request_id for debugging

#### Scenario: Request tracked with correlation ID
- **WHEN** a dialogue flow starts
- **THEN** unique request_id SHALL be generated
- **AND** request_id SHALL be included in all queries and commands
- **AND** request_id SHALL be logged for debugging

### Error Handling

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

### Retry Queue Injection

The `DialogueGenerator` constructor SHALL accept an optional `retry_queue` parameter (default None). When provided, the generator SHALL use it to defer transient failures. When None, behavior SHALL be identical to the current implementation.

#### Scenario: Generator created with retry queue
- **WHEN** `DialogueGenerator(llm_client, state_client, publisher, retry_queue=queue)` is called
- **THEN** the generator SHALL use the provided queue for deferral

#### Scenario: Generator created without retry queue
- **WHEN** `DialogueGenerator(llm_client, state_client, publisher)` is called
- **THEN** the generator SHALL handle all errors as before (log and discard)

### Heartbeat Acknowledgement

The Python service SHALL acknowledge heartbeat messages from Lua to enable connection status tracking.

#### Scenario: Heartbeat received from Lua
- **WHEN** Python receives a `system.heartbeat` message
- **THEN** Python SHALL publish `service.heartbeat.ack` back to Lua
- **AND** the ack payload SHALL include `status: "alive"` and `timestamp`

### LOG_HEARTBEAT Configuration

The Python service SHALL support a `LOG_HEARTBEAT` environment variable to control heartbeat logging verbosity.

#### Scenario: LOG_HEARTBEAT not set or false
- **WHEN** `LOG_HEARTBEAT` is not set or set to `false`
- **THEN** heartbeat messages SHALL NOT be logged (reduces log noise)
- **AND** this applies to router receive/publish logs and event handler logs

#### Scenario: LOG_HEARTBEAT set to true
- **WHEN** `LOG_HEARTBEAT=true` is set in `.env`
- **THEN** all heartbeat messages SHALL be logged at DEBUG level
- **AND** this enables debugging of connection issues

### Session-aware generate_from_event

`DialogueGenerator.generate_from_event(event, is_important=False, *, session_id=None)` SHALL accept an optional `session_id` keyword parameter. When provided, the generator SHALL pass `session_id` to all `state.execute_batch()` calls (as `session=session_id`) and all `publisher.publish()` calls (as `session=session_id`). When `None`, behavior SHALL be identical to the current broadcast mode.

#### Scenario: Session_id threads through event generation

- **WHEN** `generate_from_event(event, session_id="player_1")` is called
- **THEN** all state queries SHALL use `session="player_1"`
- **AND** all publish calls (dialogue.display, memory.update) SHALL use `session="player_1"`

#### Scenario: No session_id preserves broadcast behavior

- **WHEN** `generate_from_event(event)` is called without session_id
- **THEN** state queries and publishes SHALL broadcast to all connections

### Session-aware generate_from_instruction

`DialogueGenerator.generate_from_instruction(speaker_id, event, *, session_id=None)` SHALL accept an optional `session_id` keyword parameter with the same threading behavior as `generate_from_event`.

#### Scenario: Session_id threads through instruction generation

- **WHEN** `generate_from_instruction("42", event, session_id="player_2")` is called
- **THEN** all state queries and publishes SHALL use `session="player_2"`

### Session-aware LLM client access

`DialogueGenerator` SHALL provide a `get_llm(session_id=None)` method. When the generator was constructed with a factory function, `get_llm` SHALL call the factory. If the factory accepts a `session_id` parameter (detected via `inspect.signature`), `session_id` SHALL be passed through. If the factory does not accept `session_id`, it SHALL be called without it (backward compatible). The existing `llm` property SHALL be retained for backward compatibility, delegating to `get_llm(None)`.

#### Scenario: Factory with session_id parameter receives session

- **WHEN** the generator is constructed with a factory `def factory(session_id=...)`
- **AND** `get_llm("session_x")` is called
- **THEN** the factory SHALL receive `session_id="session_x"`

#### Scenario: Zero-arg factory still works

- **WHEN** the generator is constructed with a zero-arg factory `def factory()`
- **AND** `get_llm("session_y")` is called
- **THEN** the factory SHALL be called without arguments

### Heartbeat ack targets session

`handle_heartbeat(payload, session_id)` SHALL publish `service.heartbeat.ack` with `session=session_id` so the ack reaches only the requesting player. Config re-request (`config.request`) SHALL also target the specific session.

#### Scenario: Heartbeat ack routed to correct session

- **WHEN** session "player_3" sends a heartbeat
- **THEN** `service.heartbeat.ack` SHALL be published with `session="player_3"`

#### Scenario: Config request targets session on no sync

- **WHEN** session "player_4" sends a heartbeat
- **AND** config is not yet synced for that session
- **THEN** `config.request` SHALL be published with `session="player_4"`

## Scenarios

#### Full dialogue generation flow

WHEN a game.event is received with is_important=true
THEN speaker selection runs (filters cooldowns, picks via LLM if needed)
AND memory context is fetched for selected speaker
AND dialogue prompt is built and sent to LLM
AND dialogue.display command is sent to Lua with generated text

#### Single available speaker (fast path)

WHEN event has only one witness not on cooldown
THEN speaker is selected without LLM call
AND dialogue generation proceeds directly

#### Memory compression triggered

WHEN new_events count >= 12 for a character
THEN compression lock is acquired
AND LLM generates compressed summary
AND memory.update command is sent to Lua
AND lock is released

#### LLM timeout during dialogue

WHEN LLM call exceeds 60 seconds
THEN timeout error is caught
AND no dialogue.display command is sent
AND error is logged with request_id

#### Concurrent compression prevented

WHEN compression is already in progress for character X
THEN second compression request for X is skipped
AND log indicates "lock already held"
