## MODIFIED Requirements

### Requirement: Service channel topics (Python → Lua)

The following topics SHALL be sent by the Python service to the Lua game client:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `dialogue.display` | `speaker_id` (string/int), `dialogue` (string), `duration_ms` (int) | Display NPC dialogue (text only, no audio) |
| `tts.audio` | `speaker_id` (string/int), `audio_b64` (string), `voice_id` (string), `dialogue` (string) | Display NPC dialogue with in-engine TTS audio |
| `memory.update` | `character_id` (string), `narrative` (string) | Update character long-term memory |
| `state.query.batch` | `r` at envelope level, `queries` (array) | Batch state query (correlates via r) |

#### Scenario: dialogue.display sent with required fields

- **WHEN** `router.publish("dialogue.display", {"speaker_id": "5", "dialogue": "Hey stalker", "duration_ms": 4000})` is called
- **THEN** the Lua client receives the envelope with `t = "dialogue.display"`

#### Scenario: tts.audio sent with audio payload

- **WHEN** `router.publish("tts.audio", {"speaker_id": "5", "audio_b64": "<base64>", "voice_id": "dolg_1", "dialogue": "Stay sharp.", "dialogue_id": 3})` is called
- **THEN** the Lua client receives the envelope with `t = "tts.audio"`
- **AND** the payload contains base64-encoded OGG Vorbis audio and a monotonic dialogue_id

## ADDED Requirements

### Requirement: Documentation in ws-api.yaml includes TTS topics

The file `docs/ws-api.yaml` SHALL document the `tts.audio` topic with its payload schema, direction, and purpose.

#### Scenario: ws-api.yaml documents TTS topic

- **WHEN** `docs/ws-api.yaml` is opened
- **THEN** the `tts.audio` (Python→Lua) topic is documented with full payload field descriptions including `dialogue_id`
