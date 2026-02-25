## MODIFIED Requirements

### Requirement: Lua connects only to `talker_bridge`

Lua SHALL connect to `talker_bridge` (localhost, port 5558) via a single WebSocket connection. The existing `service-channel` (direct Lua → `talker_service` on port 5557) is removed. All topics previously sent directly to `talker_service` are now sent to `talker_bridge`, which proxies them upstream.

#### Scenario: Single connection architecture
- **WHEN** Lua initializes the WS connection
- **THEN** it connects only to `ws://localhost:5558` (the bridge)
- **AND** does NOT maintain a separate connection to `talker_service`

### Requirement: Mic control topics (Lua → `talker_bridge`)

| Topic | Payload | Purpose |
|-------|---------|---------|
| `mic.start` | `{ lang, prompt }` | Start recording |
| `mic.cancel` | `{}` | Cancel current recording |

These topics are handled locally by `talker_bridge` and are NOT proxied to `talker_service`.

#### Scenario: mic.start triggers recording
- **WHEN** `{"t":"mic.start","p":{"lang":"en","prompt":"..."}}` is received by `talker_bridge`
- **THEN** audio capture begins locally in the bridge

### Requirement: Mic status topics (`talker_bridge` → Lua)

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `mic.status` | `state` (string: "LISTENING"\|"TRANSCRIBING") | HUD status update |
| `mic.result` | `text` (string) | Transcription result |

`mic.status` originates from `talker_bridge` (for LISTENING state). TRANSCRIBING status and `mic.result` originate from `talker_service` and are proxied through the bridge to Lua.

#### Scenario: mic.result delivered with transcript
- **WHEN** transcription completes in `talker_service`
- **AND** `{"t":"mic.result","p":{"text":"Check six, stalker"}}` is sent back through the bridge
- **THEN** the Lua client receives the transcript text

## ADDED Requirements

### Requirement: Audio streaming topics (`talker_bridge` → `talker_service`)

The following topics are sent by `talker_bridge` directly to `talker_service` over the upstream WS connection. These never pass through Lua.

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `mic.audio.chunk` | `audio_b64` (string), `seq` (int) | Stream a chunk of captured audio |
| `mic.audio.end` | `context` (object: `{type: "dialogue"\|"whisper"}`) | Signal end of audio stream; includes context for dialogue routing |

#### Scenario: mic.audio.chunk sent during recording
- **WHEN** `talker_bridge` captures a chunk of audio data
- **THEN** it sends `{"t":"mic.audio.chunk","p":{"audio_b64":"...","seq":1}}` to `talker_service`

#### Scenario: mic.audio.end sent after VAD silence
- **WHEN** local VAD detects end of speech
- **THEN** `talker_bridge` sends `{"t":"mic.audio.end","p":{"context":{"type":"dialogue"}}}` to `talker_service`

### Requirement: Proxied topics (transparent relay)

All other topics (e.g., `game.event`, `player.dialogue`, `config.update`, `dialogue.display`, `memory.update`, `state.query.batch`, etc.) pass through `talker_bridge` transparently. The bridge does not inspect, modify, or route these messages — it forwards them as-is between Lua and `talker_service`.

#### Scenario: Transparent proxying
- **WHEN** Lua sends `{"t":"game.event","p":{...}}` to the bridge
- **THEN** `talker_bridge` forwards the message unchanged to `talker_service`
- **AND** any response from `talker_service` is forwarded unchanged to Lua