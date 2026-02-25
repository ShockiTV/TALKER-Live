## ADDED Requirements

### Requirement: Audio stream reception
The `talker_service` SHALL accept incoming audio stream chunks (`mic.audio.chunk`) and end-of-stream signals (`mic.audio.end`) over the WebSocket connection from `talker_bridge`.

#### Scenario: Receiving audio chunks
- **WHEN** `talker_bridge` sends `mic.audio.chunk` messages during a recording session
- **THEN** the `talker_service` buffers the base64-decoded audio data in order (by `seq`)

#### Scenario: End of stream
- **WHEN** `talker_bridge` sends `mic.audio.end`
- **THEN** the `talker_service` finalizes the audio buffer and triggers transcription

### Requirement: Whisper transcription integration
The `talker_service` SHALL integrate a Speech-to-Text (STT) provider (e.g., Whisper local model or API) to transcribe the received audio buffer into text.

#### Scenario: Successful transcription
- **WHEN** a complete audio buffer is finalized and processed by the STT provider
- **THEN** the service generates a text transcript of the audio

### Requirement: Transcription result delivery
The `talker_service` SHALL send the transcription result back through the WebSocket as a `mic.result` message, which `talker_bridge` proxies to Lua.

#### Scenario: Result sent back
- **WHEN** the STT provider returns a valid transcript
- **THEN** `talker_service` sends `{"t":"mic.result","p":{"text":"..."}}` over the WS connection
- **AND** `talker_bridge` proxies it to Lua

### Requirement: Dialogue generation from transcript
The `talker_service` SHALL use the generated transcript as player input to trigger the standard dialogue generation flow, identical to how text input from the chatbox is handled.

#### Scenario: Transcript triggers dialogue
- **WHEN** the STT provider returns a valid transcript
- **THEN** the service processes it as a `player.dialogue` or `player.whisper` event based on the `context.type` provided in the `mic.audio.end` message