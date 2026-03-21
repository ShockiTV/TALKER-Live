# ws-api-contract

## Purpose

Defines the wire protocol between the Lua game client and the Python service (and talker_bridge) over WebSocket. Supersedes `zmq-api-contract`. The canonical reference is `docs/ws-api.yaml`.

## Requirements

### Requirement: JSON envelope format

Every message exchanged over any TALKER WebSocket connection SHALL use the JSON envelope format:
```json
{"t": "<topic>", "p": <payload_object>, "r": "<request_id>", "ts": <unix_ms>}
```
Where:
- `t` (string, required): topic identifier
- `p` (object, required): message payload
- `r` (string, optional): request ID for request/response correlation
- `ts` (integer, optional): sender timestamp in Unix milliseconds

Fields `r` and `ts` MAY be omitted. No other top-level keys are defined.

#### Scenario: Envelope with all fields is valid

- **WHEN** `{"t":"game.event","p":{},"r":"req-1","ts":1700000000}` is received
- **THEN** it is parsed successfully with all four fields

#### Scenario: Envelope missing r and ts is valid

- **WHEN** `{"t":"game.event","p":{}}` is received
- **THEN** it is valid and r/ts default to nil/absent

### Requirement: Service channel topics (Lua → Python)

The following topics SHALL be accepted by the Python service from the Lua game client:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `game.event` | `event` (object), `is_important` (bool) | Game event (death, dialogue, etc.) |
| `player.dialogue` | `text` (string), `context` (object) | Player chatbox input |
| `player.whisper` | `text` (string), `context` (object) | Player whisper (companion-only) |
| `config.update` | `key` (string), `value` | Single MCM setting change |
| `config.sync` | Full config object | Full config on game load or reconnect |

#### Scenario: game.event accepted with required fields

- **WHEN** `{"t":"game.event","p":{"event":{...},"is_important":true}}` is received
- **THEN** the event handler is invoked with the event object

### Requirement: Service channel topics (Python → Lua)

The following topics SHALL be sent by the Python service to the Lua game client:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `dialogue.display` | `speaker_id` (string/int), `dialogue` (string), `duration_ms` (int), `dialogue_id` (int) | Display NPC dialogue (text only, no audio) |
| `tts.audio` | `speaker_id` (string/int), `audio_b64` (string), `voice_id` (string), `dialogue` (string), `dialogue_id` (int) | Display NPC dialogue with in-engine TTS audio |
| `memory.update` | `character_id` (string), `narrative` (string) | Update character long-term memory |
| `state.query.batch` | `r` at envelope level, `queries` (array) | Batch state query (correlates via r) |

#### Scenario: dialogue.display sent with required fields

- **WHEN** `router.publish("dialogue.display", {"speaker_id": "5", "dialogue": "Hey stalker", "duration_ms": 4000, "dialogue_id": 1})` is called
- **THEN** the Lua client receives the envelope with `t = "dialogue.display"`

#### Scenario: tts.audio sent with audio payload

- **WHEN** `router.publish("tts.audio", {"speaker_id": "5", "audio_b64": "<base64>", "voice_id": "dolg_1", "dialogue": "Stay sharp.", "dialogue_id": 2})` is called
- **THEN** the Lua client receives the envelope with `t = "tts.audio"`
- **AND** the payload contains base64-encoded OGG Vorbis audio

### Requirement: Lua connects directly to talker_service

Lua SHALL connect directly to `talker_service` via a single WebSocket connection. There is no intermediate bridge process. The connection target is determined by MCM `service_url` (default: `ws://127.0.0.1:5557/ws`).

#### Scenario: Single direct connection architecture
- **WHEN** Lua initializes the WS connection
- **THEN** it connects directly to `talker_service` (default `ws://127.0.0.1:5557/ws`)
- **AND** there is no `talker_bridge` process in the architecture

### Requirement: Mic control via native DLL

Mic control (`start`, `stop`) SHALL be handled entirely by the native `talker_audio.dll` via LuaJIT FFI. There SHALL be no `mic.start` or `mic.stop` WebSocket topics. Audio frames are streamed as `mic.audio.chunk` directly from Lua to `talker_service`.

#### Scenario: Mic start uses native DLL
- **WHEN** the player presses the mic key
- **THEN** `talker_audio.dll` begins capturing audio via PortAudio
- **AND** no `mic.start` WS message is sent

### Requirement: Mic status topics (talker_service → Lua)
The following mic status topics SHALL be sent by `talker_service` to the Lua client:
| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `mic.result` | `text` (string), `session_id` (int) | Transcription result |

`mic.status` with `RECORDING` state originates from the native DLL (not a WS topic). `mic.result` originates from `talker_service` and is sent directly to Lua.

#### Scenario: mic.result delivered with transcript
- **WHEN** transcription completes in `talker_service`
- **AND** `{"t":"mic.result","p":{"text":"Check six, stalker"}}` is sent to Lua
- **THEN** the Lua client receives the transcript text directly from the service

### Requirement: Audio streaming topics (Lua → talker_service)

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

### Requirement: State query protocol

State queries SHALL use request/response correlation via the `r` field:
1. Python sends `{"t":"state.query.batch","p":{"queries":[...]},"r":"<uuid>"}` to Lua
2. Lua responds `{"t":"state.response","p":{...},"r":"<same-uuid>"}` on the same WS connection
3. Python `WSRouter` routes the response by `r` to the pending `asyncio.Future`

#### Scenario: State query round-trip

- **WHEN** Python sends a `state.query.batch` with `r = "q-1"`
- **AND** Lua responds with `r = "q-1"`
- **THEN** the Python `StateQueryClient` receives the response payload

### Requirement: Documentation in ws-api.yaml

The file `docs/ws-api.yaml` SHALL describe all topics, envelope format, close codes, and auth requirements. It SHALL be the canonical wire protocol reference for the direct Lua ↔ `talker_service` architecture with no bridge intermediary. All direction labels SHALL use `lua→service` and `service→lua` (not `lua→bridge→service`).

#### Scenario: ws-api.yaml documents direct architecture

- **WHEN** `docs/ws-api.yaml` is opened
- **THEN** all topics are documented with direction `lua→service` or `service→lua`
- **AND** there are no references to `talker_bridge` as an intermediary
