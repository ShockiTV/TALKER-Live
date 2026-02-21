# zmq-api-contract

## Purpose

Single source of truth YAML schema file defining all ZMQ topics, directions, payload structures, shared types, and state query request/response pairs for the Lua↔Python wire protocol.

## Requirements

### Requirement: YAML schema file at docs/zmq-api.yaml

The system SHALL provide a YAML schema file at `docs/zmq-api.yaml` that defines the complete ZMQ API contract between Lua and Python.

The file SHALL contain:
- A `version` field indicating the schema version
- A `wire_format` field documenting the message framing (`"<topic> <json-payload>"`)
- A `types` section defining reusable data structures
- A `messages` section defining every ZMQ topic

#### Scenario: Schema file exists and is valid YAML

- **WHEN** `docs/zmq-api.yaml` is loaded by a YAML parser
- **THEN** it SHALL parse without errors
- **AND** it SHALL contain top-level keys `version`, `wire_format`, `types`, and `messages`

### Requirement: Shared type definitions

The `types` section SHALL define all reusable data structures used across multiple messages.

Each type SHALL specify:
- Field name as key
- Field attributes: `type` (required), `required` (bool, default false), `default` (optional), `description` (optional), `enum` (optional list), `items` (for arrays), `$ref` (for type references)

Supported primitive types: `string`, `int`, `float`, `bool`, `object`, `array`, `any`.

The following types SHALL be defined (at minimum):
- `Character`: game_id, name, faction, experience, reputation, personality, backstory, weapon, visual_faction, story_id
- `Event`: type, context, game_time_ms, world_context, witnesses, flags
- `EventFlags`: is_silent, is_idle, is_compressed, is_synthetic
- `EventContext`: actor, victim, killer, spotter, target, taunter, speaker, text, item_name, action, health_percent, from_location, to_location, companions, task_name

#### Scenario: Character type defines all fields from both codebases

- **WHEN** the `Character` type is read from `docs/zmq-api.yaml`
- **THEN** it SHALL include `game_id` (string, required), `name` (string, required)
- **AND** it SHALL include optional fields: `faction`, `experience`, `reputation`, `personality`, `backstory`, `weapon`, `visual_faction`, `story_id`

#### Scenario: Event type matches typed event structure

- **WHEN** the `Event` type is read from `docs/zmq-api.yaml`
- **THEN** it SHALL include `type` (string, with enum of all EventType values)
- **AND** it SHALL include `context` ($ref EventContext), `game_time_ms` (int), `witnesses` (array of Character), `flags` ($ref EventFlags)

### Requirement: Lua→Python message definitions

The `messages` section SHALL define all topics where Lua publishes to Python:

| Topic | Description |
|-------|-------------|
| `game.event` | Game events (death, dialogue, artifacts, etc.) |
| `player.dialogue` | Player chatbox input |
| `player.whisper` | Player whisper input |
| `config.update` | MCM setting changed |
| `config.sync` | Full config on game load |
| `system.heartbeat` | Connection health check |

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

### Requirement: Python→Lua command definitions

The `messages` section SHALL define all topics where Python publishes commands to Lua:

| Topic | Description |
|-------|-------------|
| `dialogue.display` | Display NPC dialogue |
| `memory.update` | Update character narrative memory |
| `event.store` | Store a compressed memory event |
| `config.request` | Request config sync from Lua |
| `service.heartbeat.ack` | Acknowledge heartbeat |

Each message SHALL specify: `direction: python→lua`, `description`, and `payload` with field definitions.

#### Scenario: dialogue.display message is fully defined

- **WHEN** the `dialogue.display` message is read from the schema
- **THEN** its `direction` SHALL be `python→lua`
- **AND** its `payload` SHALL define `speaker_id` (string, required), `dialogue` (string, required), `create_event` (bool, default true), `event_context` (object, optional)

#### Scenario: memory.update message is fully defined

- **WHEN** the `memory.update` message is read from the schema
- **THEN** its `payload` SHALL define `character_id` (string, required), `narrative` (string, optional), `last_event_time_ms` (int, optional)

### Requirement: State query definitions

The `messages` section SHALL define all state query request/response pairs. State queries use a pattern where Python publishes a request topic and Lua responds on `state.response`.

| Query Topic | Description |
|-------------|-------------|
| `state.query.memories` | Character memory context |
| `state.query.events` | Recent events |
| `state.query.character` | Character info by ID |
| `state.query.characters_nearby` | Characters near a position |
| `state.query.characters_alive` | Alive status for story IDs |
| `state.query.world` | Current world context |

Each state query message SHALL specify: `direction: python→lua→python`, `description`, `request` (payload fields), and `response` (response data fields).

All requests implicitly include `request_id` (string) — this SHALL NOT be listed per-query but documented once at schema level.

#### Scenario: state.query.memories is fully defined

- **WHEN** the `state.query.memories` message is read from the schema
- **THEN** its `request` SHALL define `character_id` (string, required)
- **AND** its `response` SHALL define `character_id` (string), `narrative` (string, optional), `last_update_time_ms` (int), `new_events` (array of Event)

#### Scenario: state.query.world is fully defined

- **WHEN** the `state.query.world` message is read from the schema
- **THEN** its `request` SHALL be empty (no parameters beyond request_id)
- **AND** its `response` SHALL define `loc` (string), `poi` (string, optional), `time` (object), `weather` (string), `emission` (bool), `psy_storm` (bool), `sheltering` (bool), `campfire` (string, optional), `brain_scorcher_disabled` (bool), `miracle_machine_disabled` (bool)

#### Scenario: state.query.characters_alive is fully defined

- **WHEN** the `state.query.characters_alive` message is read from the schema
- **THEN** its `request` SHALL define `ids` (array of string, required)
- **AND** its `response` SHALL be a flat object mapping story_id (string) to alive status (bool)

### Requirement: state.response envelope

The schema SHALL document the `state.response` envelope format used for all query responses:

```
state.response {"request_id": "<correlated-id>", "data": {<response-payload>}}
```

Error responses SHALL include `error` (string) instead of `data`.

#### Scenario: state.response envelope is documented

- **WHEN** the `state.response` message is read from the schema
- **THEN** it SHALL specify `direction: lua→python`
- **AND** it SHALL define `request_id` (string, required), `response_type` (string), and either `data` (object) or `error` (string)

### Requirement: Lua empty table handling note

The schema SHALL document that Lua serializes empty tables `{}` as either JSON `{}` or `[]`, and that consumers MUST handle both representations.

#### Scenario: Empty table handling is documented

- **WHEN** a developer reads the schema file
- **THEN** there SHALL be a `notes` section documenting the Lua empty table serialization behavior
- **AND** it SHALL specify that fields typed as `object` MAY arrive as `[]` when empty

### Requirement: docs/ZMQ_Message_Schema.md is removed

The file `docs/ZMQ_Message_Schema.md` SHALL be deleted, replaced entirely by `docs/zmq-api.yaml`.

#### Scenario: Old markdown file does not exist

- **WHEN** the change is applied
- **THEN** `docs/ZMQ_Message_Schema.md` SHALL NOT exist in the repository
