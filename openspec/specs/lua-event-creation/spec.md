# lua-event-creation

## Purpose

Event creation in Lua, including Event entity and interface layer event registration.

## Requirements

### Requirement: Event Creation Without World Context

The system SHALL create events without a world_context field.

Event.create() signature:
```lua
Event.create(type, context, game_time_ms, witnesses, flags)
```

Events SHALL NOT include world_context. Scene context is queried JIT during prompt building.

Trigger scripts SHALL delegate business logic (cooldown checks, importance classification) to `bin/lua/` domain modules rather than implementing them inline. The trigger scripts SHALL retain only engine callback registration, engine data fetching, and event wiring.

#### Scenario: Create death event without world_context
- **WHEN** trigger creates DEATH event via Event.create
- **THEN** event contains type, context, game_time_ms, witnesses, flags
- **AND** event does NOT contain world_context field
- **AND** cooldown check is performed via `domain.service.cooldown` CooldownManager
- **AND** importance check is performed via `domain.service.importance` module

#### Scenario: Create artifact event with cooldown delegation
- **WHEN** artifact trigger fires
- **THEN** cooldown/anti-spam check is performed via CooldownManager with slots "pickup", "use", "equip"
- **AND** the event is created only if cooldown allows it

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
- **AND** Event.describe does NOT exist

### Requirement: MAP_TRANSITION Event Context Structure

MAP_TRANSITION events SHALL include technical location IDs and travel metadata.

Context fields:
- `actor`: Character who traveled (player)
- `source`: Technical location ID of origin (e.g., `l01_escape`)
- `destination`: Technical location ID of arrival (e.g., `l02_garbage`)
- `visit_count`: Integer count of times player has visited destination
- `companions`: Array of Character objects who traveled with the player

The event SHALL NOT include `destination_description` - descriptions are resolved by Python.

#### Scenario: Map transition with companions
- **WHEN** player travels from Cordon to Garbage with companion Hip
- **THEN** event.context.source equals "l01_escape"
- **AND** event.context.destination equals "l02_garbage"
- **AND** event.context.visit_count equals number of previous visits + 1
- **AND** event.context.companions contains Hip's Character object
- **AND** event.context does NOT contain destination_description

#### Scenario: Map transition without companions
- **WHEN** player travels alone from Jupiter to Zaton
- **THEN** event.context.source equals "jupiter"
- **AND** event.context.destination equals "zaton"
- **AND** event.context.companions is empty array

#### Scenario: First visit to location
- **WHEN** player visits a location for the first time
- **THEN** event.context.visit_count equals 1

#### Scenario: Subsequent visit to location
- **WHEN** player visits a location they've been to 3 times before
- **THEN** event.context.visit_count equals 4
