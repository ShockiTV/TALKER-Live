## MODIFIED Requirements

### Requirement: Event creation function

`Event.create(type, context, game_time_ms, witnesses)` SHALL create a new event object with:
- `type` – EventType enum value
- `context` – table of key-value pairs describing the event
- `game_time_ms` – integer game timestamp
- `witnesses` – array of character objects who observed the event

The function SHALL NOT accept a `flags` parameter.

#### Scenario: Create an event without flags
- **WHEN** `Event.create("DEATH", {actor = char_a, victim = char_b}, 1000, {char_c, char_d})` is called
- **THEN** the returned event SHALL have `type = "DEATH"`, `context = {actor = char_a, victim = char_b}`, `game_time_ms = 1000`, `witnesses = {char_c, char_d}`
- **AND** the event SHALL NOT have a `flags` field

#### Scenario: Create event with empty witnesses
- **WHEN** `Event.create("EMISSION", {}, 2000, {})` is called
- **THEN** the returned event SHALL have `witnesses` as an empty array

### Requirement: Event Module Scope

The event module SHALL contain only the `Event` entity and `TEMPLATES` table. It SHALL NOT contain flags, importance logic, or speaker selection hints.

#### Scenario: No flags in event module
- **GIVEN** the event module source code
- **THEN** it SHALL NOT define or reference `flags`, `is_important`, `is_silent`, or `importance`

### Requirement: MAP_TRANSITION context

The MAP_TRANSITION event context SHALL include:
- `from` – source level name
- `to` – destination level name

No flags are needed to indicate importance — all events are treated equally in the tool-based system.

#### Scenario: MAP_TRANSITION event
- **WHEN** `Event.create("MAP_TRANSITION", {from = "l01_escape", to = "l02_garbage"}, 5000, {})` is called
- **THEN** the event SHALL have the expected type, context, and no flags

## ADDED Requirements

### Requirement: Trigger store-and-publish API

Trigger scripts SHALL use a unified `trigger.store_and_publish(event_type, context, witnesses)` function that:
1. Creates an event via `Event.create()`
2. Stores it in the speaker's memory_store (per-NPC events tier)
3. Fans out a copy to all witness NPCs' memory_stores
4. Publishes the event over WebSocket with candidates, world, and traits

#### Scenario: DEATH event store and publish
- **WHEN** `trigger.store_and_publish("DEATH", {actor = killer, victim = victim}, {npc1, npc2})` is called
- **THEN** the event SHALL be stored in killer's memory_store events tier
- **AND** the event SHALL be fanned out to npc1 and npc2's memory_stores
- **AND** the event SHALL be published over WS with `candidates`, `world`, and `traits`

#### Scenario: No flags in trigger API
- **GIVEN** the trigger API
- **THEN** `store_and_publish` SHALL NOT accept `flags` or `is_important` parameters

## REMOVED Requirements

### Requirement: Event flags parameter
**Reason**: The flags system ({is_silent, is_important}) is eliminated. Speaker selection is now handled by the LLM via tools, not by Lua-side importance flags.
**Migration**: Remove the `flags` parameter from `Event.create()`. Triggers call `trigger.store_and_publish()` instead of `trigger.talker_event_near_player()`.

### Requirement: Event importance logic
**Reason**: The `is_important_person(flags)` predicate and all importance-based gating are removed. Python now decides who speaks via tool-based dialogue.
**Migration**: Remove `domain/service/importance.lua` and all references to importance flags.
