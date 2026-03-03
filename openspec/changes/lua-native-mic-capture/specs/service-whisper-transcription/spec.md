# service-whisper-transcription (delta)

## MODIFIED Requirements

### Requirement: Audio stream reception
The `talker_service` SHALL accept incoming audio stream chunks (`mic.audio.chunk`) and end-of-stream signals (`mic.audio.end`) over the WebSocket connection from Lua (via pollnet) or from `talker_bridge` (legacy). Chunks may be Opus-encoded (`format: "opus"`) or OGG/Vorbis-encoded (`format: "ogg"`).

#### Scenario: Receiving Opus audio chunks
- **WHEN** Lua sends `mic.audio.chunk` messages with `format: "opus"` during a recording session
- **THEN** the `talker_service` buffers the base64-decoded Opus frames in order (by `seq`)
- **AND** if the `session_id` differs from `_active_session_id`, the old buffer is discarded first

#### Scenario: Receiving OGG audio chunks (legacy)
- **WHEN** `talker_bridge` sends `mic.audio.chunk` messages with `format: "ogg"` during a recording session
- **THEN** the `talker_service` buffers the base64-decoded OGG data in order (by `seq`)
- **AND** if the `session_id` differs from `_active_session_id`, the old buffer is discarded first

#### Scenario: End of stream
- **WHEN** a `mic.audio.end` message is received
- **AND** the `session_id` matches `_active_session_id`
- **THEN** the `talker_service` finalizes the audio buffer and triggers transcription

### Requirement: Whisper transcription integration
The `talker_service` SHALL integrate a Speech-to-Text (STT) provider (e.g., Whisper local model or API) to transcribe the received audio buffer into text. The service SHALL decode Opus frames to raw PCM before passing to the STT provider when `format` is `"opus"`. The local Whisper provider SHALL use the model name and beam size from service configuration rather than hardcoded defaults.

#### Scenario: Successful transcription from Opus
- **WHEN** a complete Opus audio buffer is finalized
- **THEN** the service decodes Opus frames to 16kHz mono PCM
- **AND** the PCM audio is passed to the STT provider for transcription

#### Scenario: Successful transcription from OGG (legacy)
- **WHEN** a complete OGG audio buffer is finalized
- **THEN** the service decodes OGG/Vorbis to PCM
- **AND** the PCM audio is passed to the STT provider for transcription

#### Scenario: Transcription uses configured model
- **WHEN** `WHISPER_MODEL` is set in the environment
- **THEN** the local STT provider uses the configured model for transcription

#### Scenario: Transcription uses configured beam size
- **WHEN** `WHISPER_BEAM_SIZE` is set in the environment
- **THEN** the local STT provider uses the configured beam size during decoding

### Requirement: Transcription result delivery
The `talker_service` SHALL send the transcription result back through the WebSocket as a `mic.result` message to whichever client sent the audio (Lua directly or via bridge proxy).

#### Scenario: Result sent back
- **WHEN** the STT provider returns a valid transcript
- **THEN** `talker_service` sends `{"t":"mic.result","p":{"text":"...","session_id":<id>}}` over the WS connection

## ADDED Requirements

### Requirement: Opus audio decoding
The `talker_service` audio handler SHALL decode Opus-encoded audio frames to raw 16kHz mono PCM before passing to the STT provider. Decoding SHALL use an appropriate Python Opus library (e.g., `opuslib`, `pyogg`, or equivalent).

#### Scenario: Opus frames decoded to PCM
- **WHEN** `mic.audio.end` is received for a session with `format: "opus"` chunks
- **THEN** each buffered Opus frame is decoded to 16kHz 16-bit mono PCM
- **AND** the decoded PCM is concatenated in sequence order
- **AND** the resulting PCM buffer is passed to the STT provider

#### Scenario: Opus decode failure
- **WHEN** an Opus frame fails to decode
- **THEN** the frame is skipped with a warning log
- **AND** transcription proceeds with the remaining frames
