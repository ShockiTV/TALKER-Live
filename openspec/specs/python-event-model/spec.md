# python-event-model

## Purpose

Python Event dataclass used for prompt building and event handling.

## Requirements

### Requirement: Event Model Structure

The Event dataclass SHALL include the following fields:
- `type`: str - EventType identifier
- `context`: dict - Event-specific context data
- `game_time_ms`: int - Game timestamp in milliseconds
- `witnesses`: list[Character] - List of witness characters
- `flags`: dict - Event flags (is_idle, is_silent, etc.)

The Event dataclass SHALL NOT include `world_context` or `content` fields.

#### Scenario: Event from_dict without world_context
- **WHEN** Event.from_dict() parses JSON payload
- **THEN** it extracts type, context, game_time_ms, witnesses, flags
- **AND** ignores any world_context field in payload (backward compatibility)

#### Scenario: Event creation without world_context
- **WHEN** Event is instantiated
- **THEN** it has type, context, game_time_ms, witnesses, flags attributes
- **AND** has no world_context attribute

#### Scenario: Event without content field
- **WHEN** Event is instantiated
- **THEN** it has type, context, game_time_ms, witnesses, flags attributes
- **AND** has no content attribute

### Requirement: Backward Compatible Deserialization

The system SHALL gracefully handle legacy events that include world_context.

#### Scenario: Legacy event with world_context parsed
- **WHEN** Event.from_dict() receives payload with world_context field
- **THEN** the world_context field is ignored
- **AND** Event is created successfully without that field

### Requirement: Event Context Model

The EventContext SHALL contain event-specific fields based on event type.

#### Scenario: Death event context
- **WHEN** DEATH event is parsed
- **THEN** context contains actor (killer) and victim Character objects

#### Scenario: Dialogue event context
- **WHEN** DIALOGUE event is parsed
- **THEN** context contains speaker Character and text string

#### Scenario: COMPRESSED event uses context.narrative
- **WHEN** COMPRESSED event is created
- **THEN** the narrative summary is stored in context["narrative"]
- **AND** no content field exists on the Event

### Requirement: COMPRESSED Event Type Handler

The system SHALL format COMPRESSED events by reading context.narrative.

#### Scenario: COMPRESSED event with narrative
- **WHEN** describe_event() is called on COMPRESSED event
- **AND** context.narrative contains "Encountered dangerous anomalies"
- **THEN** result contains "[COMPRESSED MEMORY]"
- **AND** result contains "Encountered dangerous anomalies"

#### Scenario: COMPRESSED event without narrative
- **WHEN** describe_event() is called on COMPRESSED event
- **AND** context.narrative is empty or missing
- **THEN** result contains "[COMPRESSED MEMORY]"
- **AND** result contains "no narrative available"

### Requirement: NarrativeCue for Time Gaps

The system SHALL use NarrativeCue dataclass for transient prompt artifacts like time gaps.

NarrativeCue fields:
- `type`: str - Cue type (e.g., "TIME_GAP")
- `message`: str - Formatted message text
- `game_time_ms`: int - For sorting with events

#### Scenario: NarrativeCue creation
- **WHEN** a time gap is detected between events
- **THEN** inject_time_gaps() creates NarrativeCue with type="TIME_GAP"
- **AND** NarrativeCue has message field with formatted time gap text
- **AND** NarrativeCue is not stored in event store

### Requirement: Model Consolidation

The system SHALL use state/models.py as the single source of truth for Character, Event, and MemoryContext.

#### Scenario: prompts/models.py imports from state
- **WHEN** prompts/models.py is loaded
- **THEN** Character, Event, MemoryContext are imported from state/models.py
- **AND** no duplicate definitions exist in prompts/models.py

### Requirement: MAP_TRANSITION Event Formatting

The `describe_event()` function SHALL format MAP_TRANSITION events with location names, visit count, companions, and destination description.

Output format: `"{actor} [and their travelling companions {companions}] traveled from {source_name} to {destination_name} {visit_text}. {destination_description}"`

Components:
- `source_name`: Human-readable name resolved from `context.source` technical ID
- `destination_name`: Human-readable name resolved from `context.destination` technical ID
- `visit_text`: "for the first time" (visit_count=1), "for the 2nd time" (2), "for the 3rd time" (3), "again" (>3)
- `companions`: Comma-separated names with "and" before last (e.g., "Hip and Fanatic")
- `destination_description`: Full description from `get_location_description()`

#### Scenario: Solo travel first visit
- **WHEN** describe_event() is called on MAP_TRANSITION event
- **AND** context.source is "l01_escape"
- **AND** context.destination is "l02_garbage"
- **AND** context.visit_count is 1
- **AND** context.companions is empty
- **THEN** result contains "traveled from Cordon to Garbage for the first time"
- **AND** result contains Garbage's location description

#### Scenario: Travel with one companion
- **WHEN** describe_event() is called on MAP_TRANSITION event
- **AND** context.companions contains one Character named "Hip"
- **THEN** result contains "and their travelling companions Hip traveled from"

#### Scenario: Travel with multiple companions
- **WHEN** describe_event() is called on MAP_TRANSITION event
- **AND** context.companions contains Characters named "Hip" and "Fanatic"
- **THEN** result contains "and their travelling companions Hip and Fanatic traveled from"

#### Scenario: Subsequent visits use ordinal text
- **WHEN** context.visit_count is 2
- **THEN** result contains "for the 2nd time"
- **WHEN** context.visit_count is 3
- **THEN** result contains "for the 3rd time"

#### Scenario: Many visits use "again"
- **WHEN** context.visit_count is greater than 3
- **THEN** result contains "again"

#### Scenario: Unknown location ID falls back gracefully
- **WHEN** context.destination is "unknown_level_id"
- **THEN** result uses "unknown_level_id" as destination name
- **AND** destination description is omitted

### Requirement: Location Description Lookup

The `get_location_description()` function SHALL return detailed location descriptions.

#### Scenario: Known location returns description
- **WHEN** get_location_description("l02_garbage") is called
- **THEN** returns description containing "Garbage" and relevant details

#### Scenario: Unknown location returns empty string
- **WHEN** get_location_description("unknown_id") is called
- **THEN** returns empty string
