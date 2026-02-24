## MODIFIED Requirements

### Requirement: tts.speak topic sent from Lua to mic_python

Lua SHALL publish `tts.speak` on the **mic WS channel** when dequeuing a TTS task. The payload SHALL include `voice_id` (string), `text` (string), and `speaker_id` (string). The message is encoded as a JSON WS envelope `{"t":"tts.speak","p":{...}}`.

#### Scenario: tts.speak payload is well-formed

- **WHEN** Lua dequeues a TTS task for speaker `"npc_wolf"` with voice `"dolg_3"` and dialogue `"Stay sharp."`
- **THEN** `mic_channel.publish("tts.speak", {voice_id="dolg_3", text="Stay sharp.", speaker_id="npc_wolf"})` is called
- **AND** the WS frame contains `{"t":"tts.speak","p":{"voice_id":"dolg_3","text":"Stay sharp.","speaker_id":"npc_wolf"}}`

### Requirement: tts.started topic sent from mic_python to Lua

mic_python SHALL send `tts.started` over the **mic WS connection** immediately before beginning audio playback. The payload SHALL include `speaker_id` (string).

#### Scenario: tts.started is sent before first audio chunk

- **WHEN** mic_python begins streaming audio for `speaker_id = "npc_wolf"`
- **THEN** `{"t":"tts.started","p":{"speaker_id":"npc_wolf"}}` is sent to the Lua client before any audio output occurs

### Requirement: tts.done topic sent from mic_python to Lua

mic_python SHALL send `tts.done` over the **mic WS connection** after the last audio chunk has been played and the sounddevice stream is closed. The payload SHALL include `speaker_id` (string).

#### Scenario: tts.done is sent after playback completes

- **WHEN** mic_python finishes streaming all audio chunks for `speaker_id = "npc_wolf"`
- **THEN** `{"t":"tts.done","p":{"speaker_id":"npc_wolf"}}` is sent to the Lua client

## ADDED Requirements

### Requirement: mic_python exposes asyncio WebSocket server

mic_python SHALL start an asyncio WebSocket server on `MIC_PORT` (default 5558). The Lua client connects to this server via `mic-ws-channel`. mic_python SHALL accept exactly one connection at a time; a second connection attempt while one is active SHALL be rejected with close code 4000.

#### Scenario: Lua client connects and is accepted

- **WHEN** the Lua client connects to `ws://localhost:5558`
- **THEN** the connection is accepted
- **AND** mic_python is ready to receive `mic.start`, `mic.cancel`, `tts.speak` frames

#### Scenario: Second connection rejected

- **WHEN** one Lua client is already connected
- **AND** a second client attempts to connect
- **THEN** the second connection is closed with code 4000

### Requirement: mic_python routes received topics to internal handlers

When a WS frame arrives, mic_python SHALL parse the JSON envelope and route by `t` field:
- `mic.start` → begin recording session
- `mic.cancel` → cancel current recording session
- `tts.speak` → enqueue TTS playback

#### Scenario: mic.start frame starts recording

- **WHEN** `{"t":"mic.start","p":{}}` is received
- **THEN** audio capture begins

## REMOVED Requirements

### Requirement: mic_python subscribes to tts.* topic prefix (ZMQ)

**Reason**: ZMQ SUB socket on port 5557 is replaced by the asyncio WS server. mic_python no longer subscribes — it receives via the WS connection.

**Migration**: Replace ZMQ `context.socket(zmq.SUB)` with `asyncio.start_server(handler, host, port)` on `MIC_PORT`.
