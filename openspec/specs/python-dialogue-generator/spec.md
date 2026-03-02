# python-dialogue-generator

## Purpose

Python orchestrator that handles the full dialogue generation flow: event reception → tool-based speaker selection and memory access → LLM call → display command. The Python service is the SOLE dialogue generation path - there is no Lua fallback. The `ConversationManager` uses a single LLM turn with tool-calling to select the speaker and fetch memory inline.

## Requirements

### Dialogue Generator Service

The system MUST provide `ConversationManager` class as the sole dialogue generation path, replacing `DialogueGenerator`. There SHALL be no `SpeakerSelector` — speaker selection is inline within the single LLM turn.

The `ConversationManager` class MUST provide:
- `async handle_event(event, session_id)` method as main entry point
- Access to state query client for fetching Lua state
- Access to LLM client with tool-calling support
- Tool definitions for `get_memories` and `background`
- Publisher for sending display commands

#### Scenario: All dialogue flows through ConversationManager
- **WHEN** any dialogue-triggering event occurs
- **THEN** dialogue generation SHALL be handled by the `ConversationManager`
- **AND** no separate speaker selection LLM call SHALL occur

#### Scenario: Service unavailable during dialogue request
- **WHEN** a dialogue request cannot be fulfilled due to service issues
- **THEN** the request SHALL fail gracefully (no dialogue displayed)
- **AND** there SHALL be no fallback to Lua-based generation

### Dialogue Request Flow

The system MUST handle dialogue in a single LLM turn:
1. Pre-fetch state batch (world, dead NPCs, candidate backgrounds)
2. Format event message with candidates and traits
3. Send to LLM with tool definitions
4. Execute tool loop (get_memories, background calls)
5. Extract speaker ID and dialogue text from LLM response
6. Clean response text and publish `dialogue.display`

#### Scenario: Single-turn dialogue generation
- **WHEN** a game event triggers dialogue
- **THEN** ONE LLM conversation turn SHALL handle speaker selection and dialogue generation
- **AND** the LLM SHALL use tools to fetch memory before generating dialogue

#### Scenario: Dialogue generated and displayed
- **WHEN** the LLM completes its turn with dialogue text
- **THEN** speaker_id and dialogue SHALL be extracted
- **AND** `dialogue.display` command SHALL be sent to Lua

### Memory Compression Trigger

The system MUST trigger compaction when any NPC's memory tier exceeds its cap. Compaction runs as background task using the fast model, separate from dialogue generation.

#### Scenario: Compaction triggered after event recording
- **WHEN** an event is recorded and a character's events tier exceeds cap 100
- **THEN** background compaction SHALL be triggered for that character
- **AND** compaction SHALL use `model_name_fast`, not the dialogue model

### Requirement: Request-Response Correlation

The WS router SHALL assign a monotonic `req_id` integer to each inbound message at dispatch time and pass it to the handler as a third positional argument. All handler functions SHALL accept `(payload, session_id, req_id)`. The `ConversationManager` methods (`handle_event`) SHALL accept an optional `req_id` keyword parameter and thread it to all internal methods.

The `dialogue_id` SHALL be assigned at the start of dialogue generation (before state queries) rather than at publish, so all dialogue-pipeline log lines can include it.

All log lines in the dialogue pipeline SHALL use a structured prefix format:
- `[R:{req_id}]` at transport/dispatch level
- `[R:{req_id} S:{session_id}]` at handler entry (omit `S:` when session is `__default__`)
- `[R:{req_id} S:{session_id} D#{dialogue_id}]` in the dialogue pipeline (omit `S:` when session is `__default__`)
- `[D#{dialogue_id}]` for background tasks (compaction) where `req_id` is not available

#### Scenario: req_id assigned at dispatch and passed to handler
- **WHEN** a WS message with topic `game.event` is received
- **THEN** `_process_message` SHALL assign a monotonic `req_id`
- **AND** the handler SHALL be called as `handler(payload, session_id, req_id)`

#### Scenario: req_id threads through dialogue generation
- **WHEN** `handle_event(event, session_id="p1", req_id=42)` is called
- **THEN** all log lines in state queries, LLM calls, tool execution, and publish SHALL include `[R:42]`

#### Scenario: dialogue_id assigned before state queries
- **WHEN** dialogue generation begins execution
- **THEN** a unique `dialogue_id` SHALL be assigned immediately
- **AND** all subsequent log lines (state fetch, LLM call, publish) SHALL include `[D#{dialogue_id}]`

#### Scenario: Full prefix with session and both IDs
- **WHEN** session is `"player_1"` and req_id=5 and dialogue_id=3
- **THEN** dialogue pipeline log lines SHALL use prefix `[R:5 S:player_1 D#3]`

#### Scenario: Default session omits S: segment
- **WHEN** session is `"__default__"` and req_id=5 and dialogue_id=3
- **THEN** dialogue pipeline log lines SHALL use prefix `[R:5 D#3]`

#### Scenario: Background compaction uses D# only
- **WHEN** compaction is triggered as a background task
- **THEN** log lines SHALL use `[D#{dialogue_id}]` prefix (no req_id since it runs detached)

#### Scenario: Non-dialogue handlers include req_id
- **WHEN** `handle_heartbeat(payload, session_id, req_id)` is called with req_id=10
- **THEN** heartbeat log lines SHALL include `[R:10]` in the prefix

#### Scenario: Config handler includes req_id and session
- **WHEN** `handle_config_update(payload, "player_2", 15)` is called
- **THEN** the log line SHALL include `[R:15 S:player_2]`

### Error Handling

The system MUST handle errors with distinction between transient and permanent failures:
- `StateQueryTimeout` errors (transient): SHALL defer the request to the retry queue if one is configured, instead of discarding
- LLM errors, `ConnectionError`, data errors (permanent): SHALL be caught, logged, and discarded as before
- If no retry queue is configured (None), timeout failures SHALL be handled as before (logged and discarded) for backward compatibility

#### Scenario: State query timeout deferred to retry queue
- **WHEN** dialogue generation raises `StateQueryTimeout`
- **AND** a retry queue is configured
- **THEN** the event SHALL be enqueued to the retry queue
- **AND** a warning SHALL be logged indicating deferral
- **AND** no dialogue.display command SHALL be sent

#### Scenario: State query timeout without retry queue (backward compat)
- **WHEN** dialogue generation raises `StateQueryTimeout`
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

The `ConversationManager` constructor SHALL accept an optional `retry_queue` parameter (default None). When provided, the manager SHALL use it to defer transient failures. When None, behavior SHALL be identical to the current implementation.

#### Scenario: Manager created with retry queue
- **WHEN** `ConversationManager(..., retry_queue=queue)` is called
- **THEN** the manager SHALL use the provided queue for deferral

#### Scenario: Manager created without retry queue
- **WHEN** `ConversationManager(...)` is called without retry_queue
- **THEN** the manager SHALL handle all errors as before (log and discard)

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

### Session-aware handle_event

`ConversationManager.handle_event(event, *, session_id=None)` SHALL accept an optional `session_id` keyword parameter. When provided, the manager SHALL pass `session_id` to all `state.execute_batch()` calls (as `session=session_id`) and all `publisher.publish()` calls (as `session=session_id`). When `None`, behavior SHALL be identical to the current broadcast mode.

#### Scenario: Session_id threads through event handling

- **WHEN** `handle_event(event, session_id="player_1")` is called
- **THEN** all state queries SHALL use `session="player_1"`
- **AND** all publish calls (dialogue.display, state.mutate.batch) SHALL use `session="player_1"`

#### Scenario: No session_id preserves broadcast behavior

- **WHEN** `handle_event(event)` is called without session_id
- **THEN** state queries and publishes SHALL broadcast to all connections

### Session-aware LLM client access

`ConversationManager` SHALL provide a `get_llm(session_id=None)` method. When the manager was constructed with a factory function, `get_llm` SHALL call the factory. If the factory accepts a `session_id` parameter (detected via `inspect.signature`), `session_id` SHALL be passed through. If the factory does not accept `session_id`, it SHALL be called without it (backward compatible). The existing `llm` property SHALL be retained for backward compatibility, delegating to `get_llm(None)`.

#### Scenario: Factory with session_id parameter receives session

- **WHEN** the manager is constructed with a factory `def factory(session_id=...)`
- **AND** `get_llm("session_x")` is called
- **THEN** the factory SHALL receive `session_id="session_x"`

#### Scenario: Zero-arg factory still works

- **WHEN** the manager is constructed with a zero-arg factory `def factory()`
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

#### Full dialogue generation flow (tool-based)

WHEN a game.event is received
THEN pre-fetch batch runs (world, dead NPCs, candidate backgrounds)
AND event message is formatted with candidates + traits
AND LLM is called with tool definitions (get_memories, background)
AND tool loop executes (LLM fetches memories as needed)
AND speaker_id and dialogue text are extracted from response
AND dialogue.display command is sent to Lua

#### LLM timeout during dialogue

WHEN LLM call exceeds 60 seconds
THEN timeout error is caught
AND no dialogue.display command is sent
AND error is logged with request_id

#### Compaction triggered after dialogue

WHEN event recording causes a character's events tier to exceed cap
THEN background compaction task is created
AND compaction uses model_name_fast
AND compaction results are written via state.mutate.batch
