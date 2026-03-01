## ADDED Requirements

### Requirement: Active session tracking
The service audio handler SHALL track an `_active_session_id`. When a `mic.audio.chunk` arrives with a new `session_id`, the handler SHALL discard the existing audio buffer and start a fresh buffer for the new session.

#### Scenario: New session discards old buffer
- **WHEN** `mic.audio.chunk` arrives with `session_id: 2`
- **AND** `_active_session_id` is `1`
- **THEN** the buffer for session 1 is discarded
- **AND** `_active_session_id` is updated to `2`
- **AND** the chunk is added to a fresh buffer

### Requirement: Stale end-of-stream rejection
The service SHALL ignore `mic.audio.end` messages whose `session_id` does not match `_active_session_id`.

#### Scenario: Stale mic.audio.end ignored
- **WHEN** `mic.audio.end` arrives with `session_id: 1`
- **AND** `_active_session_id` is `2`
- **THEN** the message is ignored (no transcription triggered)

### Requirement: Session ID in result and status payloads
`mic.result` and `mic.status` messages sent by the service SHALL include the `session_id` of the transcription session.

#### Scenario: mic.result includes session_id
- **WHEN** transcription completes for session 3
- **THEN** `{"t": "mic.result", "p": {"text": "...", "session_id": 3}}` is sent

## MODIFIED Requirements

### Requirement: Audio stream reception
The `talker_service` SHALL accept incoming audio stream chunks (`mic.audio.chunk`) and end-of-stream signals (`mic.audio.end`) over the WebSocket connection from `talker_bridge`.

#### Scenario: Receiving audio chunks
- **WHEN** `talker_bridge` sends `mic.audio.chunk` messages during a recording session
- **THEN** the `talker_service` buffers the base64-decoded audio data in order (by `seq`)
- **AND** if the `session_id` differs from `_active_session_id`, the old buffer is discarded first

#### Scenario: End of stream
- **WHEN** `talker_bridge` sends `mic.audio.end`
- **AND** the `session_id` matches `_active_session_id`
- **THEN** the `talker_service` finalizes the audio buffer and triggers transcription

### Requirement: Transcription result delivery
The `talker_service` SHALL send the transcription result back through the WebSocket as a `mic.result` message, which `talker_bridge` proxies to Lua.

#### Scenario: Result sent back
- **WHEN** the STT provider returns a valid transcript
- **THEN** `talker_service` sends `{"t":"mic.result","p":{"text":"...","session_id":<id>}}` over the WS connection
- **AND** `talker_bridge` proxies it to Lua
