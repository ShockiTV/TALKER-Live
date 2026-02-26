## ADDED Requirements

### Requirement: Audio capture without transcription
`talker_bridge` (formerly `mic_python`) SHALL capture audio from the user's microphone without attempting to transcribe it locally.

#### Scenario: Capturing audio
- **WHEN** the user presses the push-to-talk hotkey (via `mic.start` from Lua)
- **THEN** `talker_bridge` begins recording audio from the default microphone device

### Requirement: Local Voice Activity Detection (VAD)
`talker_bridge` SHALL perform local silence detection using VAD (e.g., `webrtcvad` or energy-based threshold) to determine when the user has stopped speaking.

#### Scenario: Detecting end of speech
- **WHEN** audio capture is active
- **AND** the VAD detects sustained silence (e.g., 1-2 seconds)
- **THEN** `talker_bridge` ends the recording session and sends `mic.audio.end`

### Requirement: Audio streaming to service
`talker_bridge` SHALL stream captured audio data directly to `talker_service` over the bridge's upstream WebSocket connection, bypassing Lua entirely.

#### Scenario: Streaming audio chunks
- **WHEN** `talker_bridge` captures a chunk of audio data
- **THEN** it compresses the chunk as OGG/Vorbis, base64-encodes it, and sends a `mic.audio.chunk` message (with `format: "ogg"`) to `talker_service`

#### Scenario: End of audio stream
- **WHEN** VAD detects end of speech or the user releases push-to-talk
- **THEN** `talker_bridge` sends a `mic.audio.end` message to `talker_service`

### Requirement: WS proxy for Lua traffic
`talker_bridge` SHALL transparently proxy all non-mic WebSocket messages between Lua and `talker_service`.

#### Scenario: Proxying game events
- **WHEN** Lua sends a message (e.g., `game.event`, `player.dialogue`) to `talker_bridge`
- **AND** the topic is not a mic-handled topic (`mic.start`, `mic.cancel`)
- **THEN** `talker_bridge` forwards it to `talker_service` unchanged

#### Scenario: Proxying service responses
- **WHEN** `talker_service` sends a message (e.g., `dialogue.display`, `memory.update`) to `talker_bridge`
- **THEN** `talker_bridge` forwards it to Lua unchanged

### Requirement: Standalone executable build
`talker_bridge` SHALL be buildable as a standalone executable (`.exe`) that does not require a full Python environment or heavy dependencies like PyTorch or Whisper models.

#### Scenario: Building the executable
- **WHEN** the build script is executed
- **THEN** a lightweight `.exe` is generated containing audio capture, VAD, and WS proxy logic