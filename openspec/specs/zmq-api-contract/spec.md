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

### Requirement: state.query.batch message definition

The `messages` section SHALL define the `state.query.batch` topic with `direction: python→lua→python`.

The `request` payload SHALL define:
- `request_id` (string, required): Unique correlation ID
- `queries` (array, required): Ordered array of sub-query objects

Each sub-query SHALL define:
- `id` (string, required): Unique identifier within the batch
- `resource` (string, required): Resource name in `store.*` or `query.*` format
- `params` (object, optional): Resource-specific parameters
- `filter` (object, optional): MongoDB-style filter document
- `sort` (object, optional): Sort specification
- `limit` (integer, optional): Maximum results
- `fields` (array of string, optional): Field projection paths

The `response` payload SHALL define:
- `request_id` (string, required): Correlated to the request
- `results` (object, required): Map of sub-query ID to result object containing `ok` (bool) and either `data` or `error` (string)

#### Scenario: state.query.batch is fully defined
- **WHEN** the `state.query.batch` message is read from the schema
- **THEN** its `direction` SHALL be `python→lua→python`
- **AND** its `request` SHALL define `request_id` and `queries` array with sub-query schema
- **AND** its `response` SHALL define `request_id` and `results` map

### Requirement: Filter document type definition

The `types` section SHALL define a `FilterDocument` type documenting all supported operators:
- Comparison: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`
- Set: `$in`, `$nin`
- String: `$regex`, `$regex_flags`
- Existence: `$exists`
- Array: `$elemMatch`, `$size`, `$all`
- Logical: `$and`, `$or`, `$not`
- Reference: `$ref:<id>.<path>` string syntax

#### Scenario: FilterDocument type is defined in schema
- **WHEN** the `FilterDocument` type is read from `docs/zmq-api.yaml`
- **THEN** it SHALL list all supported operators with descriptions and value types

### Requirement: Resource registry documentation

The schema SHALL document the available resources and their parameters in a `resources` section or as part of the `state.query.batch` message definition.

#### Scenario: All resources documented
- **WHEN** a developer reads the `state.query.batch` definition
- **THEN** they SHALL find documentation for `store.events`, `store.memories`, `store.personalities`, `store.backstories`, `store.levels`, `store.timers`, `query.character`, `query.characters_nearby`, `query.characters_alive`, and `query.world`
- **AND** each resource SHALL list its required and optional `params`

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
