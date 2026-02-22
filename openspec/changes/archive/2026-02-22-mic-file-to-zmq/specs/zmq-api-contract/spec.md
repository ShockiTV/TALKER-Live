## MODIFIED Requirements

### Requirement: Lua→Python message definitions

The `messages` section SHALL define all topics where Lua publishes to Python (and mic_python):

| Topic | Description |
|-------|-------------|
| `game.event` | Game events (death, dialogue, artifacts, etc.) |
| `player.dialogue` | Player chatbox input |
| `player.whisper` | Player whisper input |
| `config.update` | MCM setting changed |
| `config.sync` | Full config on game load |
| `system.heartbeat` | Connection health check |
| `mic.start` | Start microphone recording session |
| `mic.stop` | Stop microphone recording session |

Each message SHALL specify: `direction: lua→python`, `description`, and `payload` with field definitions.

#### Scenario: game.event message is fully defined

- **WHEN** the `game.event` message is read from the schema
- **THEN** its `direction` SHALL be `lua→python`
- **AND** its `payload` SHALL define `event` ($ref Event, required) and `is_important` (bool, default false)

#### Scenario: player.dialogue message is fully defined

- **WHEN** the `player.dialogue` message is read from the schema
- **THEN** its `payload` SHALL define `text` (string, required) and `context` (object, optional)

#### Scenario: system.heartbeat message is fully defined

- **WHEN** the `system.heartbeat` message is read from the schema
- **THEN** its `payload` SHALL define `game_time_ms` (int) and `status` (string)

#### Scenario: mic.start message is fully defined

- **WHEN** the `mic.start` message is read from the schema
- **THEN** its `direction` SHALL be `lua→mic_python`
- **AND** its `payload` SHALL define `lang` (string, required) and `prompt` (string, optional)

#### Scenario: mic.stop message is fully defined

- **WHEN** the `mic.stop` message is read from the schema
- **THEN** its `direction` SHALL be `lua→mic_python`
- **AND** its `payload` SHALL be an empty object

## ADDED Requirements

### Requirement: mic_python→Lua message definitions

The `messages` section SHALL define all topics where mic_python publishes to Lua:

| Topic | Description |
|-------|-------------|
| `mic.status` | Microphone recording status update |
| `mic.result` | Transcription result text |

Each message SHALL specify: `direction: mic_python→lua`, `description`, and `payload` with field definitions.

#### Scenario: mic.status message is fully defined

- **WHEN** the `mic.status` message is read from the schema
- **THEN** its `direction` SHALL be `mic_python→lua`
- **AND** its `payload` SHALL define `status` (string, required, enum: `["LISTENING", "TRANSCRIBING"]`)

#### Scenario: mic.result message is fully defined

- **WHEN** the `mic.result` message is read from the schema
- **THEN** its `direction` SHALL be `mic_python→lua`
- **AND** its `payload` SHALL define `text` (string, required)
