# lua-event-creation

## Purpose

Event creation in Lua, including Event entity and interface layer event registration.

## Requirements

### Requirement: Event creation function

`Event.create(type, context, game_time_ms, witnesses)` SHALL create a new event object with:
- `type` – EventType enum value
- `context` – table of key-value pairs describing the event
- `game_time_ms` – integer game timestamp
- `witnesses` – array of character objects who observed the event

The function SHALL NOT accept a `flags` parameter.

Trigger scripts SHALL delegate business logic (cooldown checks) to `bin/lua/` domain modules rather than implementing them inline. The trigger scripts SHALL retain only engine callback registration, engine data fetching, and event wiring.

#### Scenario: Create an event without flags
- **WHEN** `Event.create("DEATH", {actor = char_a, victim = char_b}, 1000, {char_c, char_d})` is called
- **THEN** the returned event SHALL have `type = "DEATH"`, `context = {actor = char_a, victim = char_b}`, `game_time_ms = 1000`, `witnesses = {char_c, char_d}`
- **AND** the event SHALL NOT have a `flags` field

#### Scenario: Create event with empty witnesses
- **WHEN** `Event.create("EMISSION", {}, 2000, {})` is called
- **THEN** the returned event SHALL have `witnesses` as an empty array

#### Scenario: Create artifact event with cooldown delegation
- **WHEN** artifact trigger fires
- **THEN** cooldown/anti-spam check is performed via CooldownManager with slots "pickup", "use", "equip"
- **AND** the event is created only if cooldown allows it

### Requirement: Event Serialization Without World Context

The system SHALL serialize events for WS without world_context field.

#### Scenario: Event serialized to JSON
- **WHEN** event is published via WS
- **THEN** JSON payload includes type, context, game_time_ms, witnesses
- **AND** JSON payload does NOT include world_context key or flags key

### Requirement: Event Module Scope

The Event module SHALL contain only the `Event` entity and `TEMPLATES` table. It SHALL NOT contain flags, importance logic, or speaker selection hints.

Event module provides:
- `Event.create(type, context, game_time_ms, witnesses)` - create events
- `Event.TYPE` - EventType enum reference
- `Event.get_involved_characters(event)` - extract characters from context
- `Event.is_junk_event(event)` - check if low-value for narrative
- `Event.was_conversation(event)` - check if dialogue event
- `Event.was_witnessed_by(event, character_id)` - witness check

Event module does NOT provide text rendering (handled by Python).

#### Scenario: No flags in event module
- **GIVEN** the event module source code
- **THEN** it SHALL NOT define or reference `flags`, `is_important`, `is_silent`, or `importance`

### Requirement: MAP_TRANSITION context

The MAP_TRANSITION event context SHALL include:
- `from` – source level name
- `to` – destination level name

No flags are stored on the Event entity itself. Importance is evaluated at the trigger level (via `importance.is_important_person()`) to decide `store_event` vs `publish_event` — not carried as event data.

#### Scenario: MAP_TRANSITION event
- **WHEN** `Event.create("MAP_TRANSITION", {from = "l01_escape", to = "l02_garbage"}, 5000, {})` is called
- **THEN** the event SHALL have the expected type, context, and no flags

### Requirement: Trigger store / publish API

The `interface/trigger.lua` module SHALL export two event-creation functions:

1. `trigger.store_event(event_type, context, witnesses)` — creates an Event, stores it in the speaker's memory_store events tier, and fans out to all witness NPCs. Does NOT publish over WS.
2. `trigger.publish_event(event_type, context, witnesses)` — calls `store_event` internally, then publishes to the Python service via `publisher.send_game_event(event, candidates, world, traits)`.

Trigger scripts decide which to call based on the consolidated flow: cooldown-active → `store_event`; importance or chance passes → `publish_event`; otherwise → `store_event`. The `importance.is_important_person(flags)` predicate in `domain/service/importance.lua` is used by trigger scripts to gate publish vs store — important characters always trigger dialogue regardless of the chance roll.

Neither function accepts a `flags` or `is_important` parameter. Events are created with an empty flags table `{}`.

#### Scenario: DEATH event store only (cooldown active)
- **WHEN** cooldown is active and `trigger.store_event(EventType.DEATH, context, witnesses)` is called
- **THEN** the event SHALL be stored in killer's memory_store events tier
- **AND** the event SHALL be fanned out to witnesses' memory_stores
- **AND** no WS publish SHALL occur

#### Scenario: DEATH event publish (importance or chance)
- **WHEN** cooldown passes and importance or chance succeeds
- **AND** `trigger.publish_event(EventType.DEATH, context, witnesses)` is called
- **THEN** the event SHALL be stored in memory (same as store_event)
- **AND** `publisher.send_game_event(event, candidates, world, traits)` SHALL be called

#### Scenario: No flags in trigger API
- **GIVEN** the trigger API functions `store_event` and `publish_event`
- **THEN** neither SHALL accept `flags` or `is_important` parameters
- **AND** the old `store_and_publish` function SHALL NOT exist on the trigger module
