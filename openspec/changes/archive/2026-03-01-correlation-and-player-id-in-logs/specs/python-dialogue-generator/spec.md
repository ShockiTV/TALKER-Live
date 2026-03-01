## MODIFIED Requirements

### Requirement: Request-Response Correlation

The WS router SHALL assign a monotonic `req_id` integer to each inbound message at dispatch time and pass it to the handler as a third positional argument. All handler functions SHALL accept `(payload, session_id, req_id)`. The `DialogueGenerator` methods (`generate_from_event`, `generate_from_instruction`) SHALL accept an optional `req_id` keyword parameter and thread it to all internal methods.

The `dialogue_id` SHALL be assigned at the start of `_generate_dialogue_for_speaker` (before state queries) rather than at `_publish_dialogue`, so all dialogue-pipeline log lines can include it.

All log lines in the dialogue pipeline SHALL use a structured prefix format:
- `[R:{req_id}]` at transport/dispatch level
- `[R:{req_id} S:{session_id}]` at handler entry (omit `S:` when session is `__default__`)
- `[R:{req_id} S:{session_id} D#{dialogue_id}]` in the dialogue pipeline (omit `S:` when session is `__default__`)
- `[D#{dialogue_id}]` for background tasks (memory compression) where `req_id` is not available

#### Scenario: req_id assigned at dispatch and passed to handler
- **WHEN** a WS message with topic `game.event` is received
- **THEN** `_process_message` SHALL assign a monotonic `req_id`
- **AND** the handler SHALL be called as `handler(payload, session_id, req_id)`

#### Scenario: req_id threads through dialogue generation
- **WHEN** `generate_from_event(event, session_id="p1", req_id=42)` is called
- **THEN** all log lines in speaker selection, state queries, LLM calls, and publish SHALL include `[R:42]`

#### Scenario: dialogue_id assigned before state queries
- **WHEN** `_generate_dialogue_for_speaker` begins execution
- **THEN** a unique `dialogue_id` SHALL be assigned immediately
- **AND** all subsequent log lines (state fetch, LLM call, publish) SHALL include `[D#{dialogue_id}]`

#### Scenario: Full prefix with session and both IDs
- **WHEN** session is `"player_1"` and req_id=5 and dialogue_id=3
- **THEN** dialogue pipeline log lines SHALL use prefix `[R:5 S:player_1 D#3]`

#### Scenario: Default session omits S: segment
- **WHEN** session is `"__default__"` and req_id=5 and dialogue_id=3
- **THEN** dialogue pipeline log lines SHALL use prefix `[R:5 D#3]`

#### Scenario: Background memory compression uses D# only
- **WHEN** memory compression is triggered as a background task
- **THEN** log lines SHALL use `[D#{dialogue_id}]` prefix (no req_id since it runs detached)

#### Scenario: Non-dialogue handlers include req_id
- **WHEN** `handle_heartbeat(payload, session_id, req_id)` is called with req_id=10
- **THEN** heartbeat log lines SHALL include `[R:10]` in the prefix

#### Scenario: Config handler includes req_id and session
- **WHEN** `handle_config_update(payload, "player_2", 15)` is called
- **THEN** the log line SHALL include `[R:15 S:player_2]`
