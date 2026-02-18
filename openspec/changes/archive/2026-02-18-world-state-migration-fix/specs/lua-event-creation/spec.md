# lua-event-creation

## Purpose

Event creation in Lua, including Event entity and interface layer event registration.

## ADDED Requirements

### Requirement: Event Creation Without World Context

The system SHALL create events without a world_context field.

Event.create() signature:
```lua
Event.create(type, context, game_time_ms, witnesses, flags)
```

Events SHALL NOT include world_context. Scene context is queried JIT during prompt building.

#### Scenario: Create death event without world_context
- **WHEN** trigger creates DEATH event via Event.create
- **THEN** event contains type, context, game_time_ms, witnesses, flags
- **AND** event does NOT contain world_context field

#### Scenario: Create dialogue event without world_context
- **WHEN** talker creates DIALOGUE event
- **THEN** event structure has no world_context
- **AND** content derived from type and context only

#### Scenario: Interface layer does not query world context
- **WHEN** interface.lua processes an event trigger
- **THEN** it does NOT call query.describe_world()
- **AND** passes nil or omits world_context parameter

### Requirement: Event Serialization Without World Context

The system SHALL serialize events for ZMQ without world_context field.

#### Scenario: Event serialized to JSON
- **WHEN** event is published via ZMQ
- **THEN** JSON payload includes type, context, game_time_ms, witnesses, flags
- **AND** JSON payload does NOT include world_context key

### Requirement: Event Module Scope

The Event module SHALL focus on event creation and metadata, not text rendering.

Event module provides:
- `Event.create(type, context, game_time_ms, witnesses, flags)` - create events
- `Event.TYPE` - EventType enum reference
- `Event.get_involved_characters(event)` - extract characters from context
- `Event.is_junk_event(event)` - check if low-value for narrative
- `Event.was_conversation(event)` - check if dialogue event
- `Event.was_witnessed_by(event, character_id)` - witness check

Event module does NOT provide text rendering (handled by Python).

#### Scenario: Event module exports creation functions
- **WHEN** Event module is loaded
- **THEN** Event.create is available
- **AND** Event.TYPE is available
- **AND** Event.get_involved_characters is available

#### Scenario: Event module does not export describe functions
- **WHEN** Event module is loaded
- **THEN** Event.describe is nil
- **AND** Event.describe_short is nil

