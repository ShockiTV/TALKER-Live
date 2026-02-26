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

### Requirement: Mic channel topics (Lua → talker_bridge)

The following topics SHALL be sent by the Lua game client to talker_bridge:

| Topic | Payload | Purpose |
|-------|---------|---------|
| `mic.start` | `{}` | Start recording |
| `mic.cancel` | `{}` | Cancel current recording |

#### Scenario: mic.start triggers recording

- **WHEN** `{"t":"mic.start","p":{}}` is received by talker_bridge
- **THEN** audio capture begins

### Requirement: Mic channel topics (talker_bridge → Lua)

The following topics SHALL be sent by talker_bridge to the Lua game client:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `mic.status` | `state` (string: "LISTENING"\|"TRANSCRIBING") | HUD status update |
| `mic.result` | `text` (string) | Transcription result |

#### Scenario: mic.result delivered with transcript

- **WHEN** transcription completes
- **AND** `{"t":"mic.result","p":{"text":"Check six, stalker"}}` is sent
- **THEN** the Lua client receives the transcript text

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

The file `docs/ws-api.yaml` SHALL describe all topics, envelope format, close codes, and auth requirements. It SHALL replace `docs/zmq-api.yaml` as the canonical wire protocol reference. This includes the `tts.audio` topic (Python→Lua) and mic channel TTS topics (`tts.speak`, `tts.started`, `tts.done`).

#### Scenario: ws-api.yaml documents service topics

- **WHEN** `docs/ws-api.yaml` is opened
- **THEN** all topics from the service and mic channels are documented with their payload schemas
- **AND** the `tts.audio` topic is documented with `speaker_id`, `audio_b64`, `voice_id`, `dialogue`, and `dialogue_id` fields
