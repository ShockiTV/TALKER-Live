# ws-api-contract

## MODIFIED Requirements

### Requirement: Lua connects only to talker_bridge

**RENAMED**: FROM: "Lua connects only to talker_bridge" TO: "Lua connects directly to talker_service"

Lua SHALL connect directly to `talker_service` via a single WebSocket connection. There is no intermediate bridge process. The connection target is determined by MCM `service_url` (default: `ws://127.0.0.1:5557/ws`).

#### Scenario: Single direct connection architecture
- **WHEN** Lua initializes the WS connection
- **THEN** it connects directly to `talker_service` (default `ws://127.0.0.1:5557/ws`)
- **AND** there is no `talker_bridge` process in the architecture

### Requirement: Mic control topics (Lua → talker_bridge)

**RENAMED**: FROM: "Mic control topics (Lua → talker_bridge)" TO: "Mic control via native DLL"

Mic control (`start`, `stop`) SHALL be handled entirely by the native `talker_audio.dll` via LuaJIT FFI. There SHALL be no `mic.start` or `mic.stop` WebSocket topics. Audio frames are streamed as `mic.audio.chunk` directly from Lua to `talker_service`.

#### Scenario: Mic start uses native DLL
- **WHEN** the player presses the mic key
- **THEN** `talker_audio.dll` begins capturing audio via PortAudio
- **AND** no `mic.start` WS message is sent

### Requirement: Mic status topics (talker_bridge → Lua)

**RENAMED**: FROM: "Mic status topics (talker_bridge → Lua)" TO: "Mic status topics (talker_service → Lua)"

The following mic status topics SHALL be sent by `talker_service` to the Lua client:
| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `mic.result` | `text` (string), `session_id` (int) | Transcription result |

`mic.status` with `RECORDING` state originates from the native DLL (not a WS topic). `mic.result` originates from `talker_service` and is sent directly to Lua.

#### Scenario: mic.result delivered with transcript
- **WHEN** transcription completes in `talker_service`
- **AND** `{"t":"mic.result","p":{"text":"Check six, stalker"}}` is sent to Lua
- **THEN** the Lua client receives the transcript text directly from the service

### Requirement: Audio streaming topics (talker_bridge → talker_service)

**RENAMED**: FROM: "Audio streaming topics (talker_bridge → talker_service)" TO: "Audio streaming topics (Lua → talker_service)"

The following audio streaming topics SHALL be sent by the Lua game client directly to `talker_service` over the WebSocket connection:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `mic.audio.chunk` | `audio_b64` (string), `seq` (int), `format` (string: "opus"), `session_id` (int) | Stream a chunk of captured audio |
| `mic.audio.end` | `context` (object: `{type: "dialogue"\|"whisper"}`), `session_id` (int) | Signal end of audio stream |

#### Scenario: mic.audio.chunk sent during recording
- **WHEN** the native DLL captures an Opus frame and Lua polls it
- **THEN** Lua sends `{"t":"mic.audio.chunk","p":{"audio_b64":"...","seq":1,"format":"opus","session_id":1}}` directly to `talker_service`

#### Scenario: mic.audio.end sent after VAD silence
- **WHEN** native DLL VAD detects end of speech
- **THEN** Lua sends `{"t":"mic.audio.end","p":{"context":{"type":"dialogue"},"session_id":1}}` directly to `talker_service`

### Requirement: Proxied topics (transparent relay)

**REMOVED**

**Reason**: With no bridge, there is no proxy layer. All topics flow directly between Lua and `talker_service`.
**Migration**: Remove all "proxied topics" references. Topics are simply "Lua → service" or "service → Lua".

### Requirement: Documentation in ws-api.yaml

The file `docs/ws-api.yaml` SHALL describe all topics, envelope format, close codes, and auth requirements. It SHALL document the direct Lua ↔ `talker_service` architecture with no bridge intermediary. All direction labels SHALL use `lua→service` and `service→lua` (not `lua→bridge→service`).

#### Scenario: ws-api.yaml documents direct architecture
- **WHEN** `docs/ws-api.yaml` is opened
- **THEN** all topics are documented with direction `lua→service` or `service→lua`
- **AND** there are no references to `talker_bridge` as an intermediary
