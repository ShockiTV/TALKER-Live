# ws-api-contract (delta)

## MODIFIED Requirements

### Requirement: Service channel topics (Lua → Python)

The following topics SHALL be accepted by the Python service from the Lua game client:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `game.event` | `event` (object), `is_important` (bool) | Game event (death, dialogue, etc.) |
| `player.dialogue` | `text` (string), `context` (object) | Player chatbox input |
| `player.whisper` | `text` (string), `context` (object) | Player whisper (companion-only) |
| `config.update` | `key` (string), `value` | Single MCM setting change |
| `config.sync` | Full config object | Full config on game load or reconnect |
| `system.heartbeat` | `game_time` (int) | Connection health check |

All topic handlers SHALL receive `(payload: dict, session_id: str)` where `session_id` identifies the player session that sent the message. The `session_id` is derived from the WebSocket connection, not from the message envelope.

#### Scenario: game.event handler receives session context

- **WHEN** `{"t":"game.event","p":{"event":{...},"is_important":true}}` is received from session "alice"
- **THEN** the event handler SHALL be invoked with `(payload, "alice")`

#### Scenario: config.sync scoped to sender session

- **WHEN** `{"t":"config.sync","p":{...}}` is received from session "bob"
- **THEN** the config sync handler SHALL apply the config to bob's session only

### Requirement: Service channel topics (Python → Lua)

The following topics SHALL be sent by the Python service to the Lua game client:

| Topic | Payload fields | Purpose |
|-------|---------------|---------|
| `dialogue.display` | `speaker_id`, `dialogue`, `game_time_ms`, etc. | Display dialogue for an NPC |
| `memory.update` | `character_id`, `narrative`, etc. | Update character's long-term memory |
| `state.query.batch` | `request_id`, `queries` | Batch state query |
| `config.request` | `reason` | Request config sync from Lua |
| `service.heartbeat.ack` | `game_time` | Heartbeat acknowledgment |
| `tts.audio` | `speaker_id`, `dialogue`, `audio_base64`, etc. | TTS audio with dialogue |

Outbound messages that are player-specific (dialogue.display, memory.update, state.query.batch, tts.audio) SHALL be published with `session=session_id` to route to the correct player's connection.

#### Scenario: Dialogue display routed to correct session

- **WHEN** dialogue is generated for session "alice"
- **THEN** `dialogue.display` SHALL be published with `session="alice"`
- **AND** session "bob" SHALL NOT receive alice's dialogue
