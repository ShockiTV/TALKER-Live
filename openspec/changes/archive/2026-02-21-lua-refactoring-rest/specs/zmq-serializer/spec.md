## ADDED Requirements

### Requirement: Serializer module exists at infra/zmq/serializer.lua

The system SHALL provide `infra/zmq/serializer.lua` containing functions to convert domain objects (Character, Event, Context) to wire-format tables suitable for JSON serialization over ZMQ. The module SHALL have zero engine dependencies.

#### Scenario: Module loads without engine
- **WHEN** `require("infra.zmq.serializer")` is called outside the STALKER engine
- **THEN** the module loads successfully

### Requirement: serialize_character converts Character to wire format

The module SHALL provide `serializer.serialize_character(char)` that converts a Character object to a flat table with string `game_id`.

#### Scenario: Character serialized
- **WHEN** a Character with `game_id=123, name="Wolf", faction="Loner", experience="veteran", reputation="Good", personality="loner.1", backstory="generic.5", weapon="AK-74"` is serialized
- **THEN** the result contains all fields with `game_id` as a string (`"123"`)

#### Scenario: Nil character returns nil
- **WHEN** `serializer.serialize_character(nil)` is called
- **THEN** it returns `nil`

#### Scenario: Visual faction preserved
- **WHEN** a Character has `visual_faction = "Duty"`
- **THEN** the serialized result includes `visual_faction = "Duty"`

### Requirement: serialize_context converts event context

The module SHALL provide `serializer.serialize_context(context)` that converts an event context table, recursively serializing any Character objects found in known character keys.

#### Scenario: Context with character fields
- **WHEN** context has `actor` and `victim` as Character objects
- **THEN** both are serialized via `serialize_character`
- **AND** non-character fields are copied as-is

#### Scenario: Context with companions array
- **WHEN** context has `companions` as an array of Character objects
- **THEN** each companion is serialized via `serialize_character`

#### Scenario: Nil context returns empty table
- **WHEN** `serializer.serialize_context(nil)` is called
- **THEN** it returns `{}`

#### Scenario: Character keys recognized
- **WHEN** context fields `victim`, `killer`, `actor`, `spotter`, `target`, `taunter`, `speaker` contain Character objects (tables with `game_id`)
- **THEN** each is serialized via `serialize_character`

### Requirement: serialize_event converts Event to wire format

The module SHALL provide `serializer.serialize_event(event)` that converts an Event object, including serializing nested context characters and witness arrays.

#### Scenario: Event with witnesses
- **WHEN** an event has 3 witnesses as Character objects
- **THEN** each witness is serialized via `serialize_character`

#### Scenario: Event preserves all fields
- **WHEN** an event with type, content, context, game_time_ms, world_context, witnesses, and flags is serialized
- **THEN** all fields are present in the result

#### Scenario: Nil event returns nil
- **WHEN** `serializer.serialize_event(nil)` is called
- **THEN** it returns `nil`

### Requirement: serialize_events batch conversion

The module SHALL provide `serializer.serialize_events(events)` that converts an array of events.

#### Scenario: Array of events serialized
- **WHEN** an array of 3 events is passed
- **THEN** it returns an array of 3 serialized events

#### Scenario: Nil events returns empty array
- **WHEN** `serializer.serialize_events(nil)` is called
- **THEN** it returns `{}`

### Requirement: Wire format matches existing protocol

The serialized output SHALL produce byte-identical JSON when encoded, compared to the existing inline serialization in `talker_zmq_query_handlers.script`. No fields SHALL be added, removed, or renamed.

#### Scenario: Character wire format unchanged
- **WHEN** a Character is serialized by the new module
- **AND** the same Character is serialized by the old inline code
- **THEN** both produce identical JSON when encoded

#### Scenario: Event wire format unchanged
- **WHEN** an Event is serialized by the new module
- **AND** the same Event is serialized by the old inline code
- **THEN** both produce identical JSON when encoded
