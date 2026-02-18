# python-event-model

## Purpose

Python Event dataclass used for prompt building and event handling.

## ADDED Requirements

### Requirement: Event Model Without World Context

The Event dataclass SHALL NOT include a world_context field.

Event fields:
- `type`: str - EventType identifier
- `context`: EventContext - Event-specific context data
- `game_time_ms`: int - Game timestamp in milliseconds
- `witnesses`: list[str] - List of witness character IDs
- `flags`: dict - Event flags (is_idle, is_silent, etc.)

#### Scenario: Event from_dict without world_context
- **WHEN** Event.from_dict() parses JSON payload
- **THEN** it extracts type, context, game_time_ms, witnesses, flags
- **AND** ignores any world_context field in payload (backward compatibility)

#### Scenario: Event creation without world_context
- **WHEN** Event is instantiated
- **THEN** it has type, context, game_time_ms, witnesses, flags attributes
- **AND** has no world_context attribute

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

### Requirement: Event Model Without Content Field

The Event dataclass SHALL NOT include a content field. COMPRESSED events store their summary in context.narrative.

#### Scenario: Event without content field
- **WHEN** Event is instantiated
- **THEN** it has type, context, game_time_ms, witnesses, flags attributes
- **AND** has no content attribute

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

#### Scenario: NarrativeCue creation
- **WHEN** a time gap is detected between events
- **THEN** inject_time_gaps() creates NarrativeCue with cue_type="TIME_GAP"
- **AND** NarrativeCue has message field with formatted time gap text
- **AND** NarrativeCue is not stored in event store

### Requirement: Model Consolidation

The system SHALL use state/models.py as the single source of truth for Character, Event, and MemoryContext.

#### Scenario: prompts/models.py imports from state
- **WHEN** prompts/models.py is loaded
- **THEN** Character, Event, MemoryContext are imported from state/models.py
- **AND** no duplicate definitions exist in prompts/models.py

