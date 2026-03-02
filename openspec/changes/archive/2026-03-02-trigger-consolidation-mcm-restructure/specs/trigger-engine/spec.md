# trigger-engine

## Purpose

Consolidated trigger flow for all 13 trigger types. Splits the trigger API into `store_event` (memory only) and `publish_event` (memory + WS dialogue), provides a shared chance utility, and uses dynamic MCM reads at trigger time.

## Requirements

### Requirement: store_event function

The `interface/trigger.lua` module SHALL export `store_event(event_type, context, witnesses)` which creates an Event, stores it in the speaker's memory via `memory_store_v2:store_event()`, and fans out to witnesses via `memory_store_v2:fan_out()`. It SHALL NOT publish to Python via WebSocket.

#### Scenario: Store-only event created
- **WHEN** `trigger.store_event(EventType.DEATH, context, witnesses)` is called
- **THEN** an Event SHALL be created with the given type and context
- **AND** the event SHALL be stored in `context.actor.game_id`'s memory
- **AND** the event SHALL be fanned out to all witnesses
- **AND** NO WebSocket message SHALL be sent

#### Scenario: Store event without witnesses
- **WHEN** `trigger.store_event(EventType.ARTIFACT, context, {})` is called with empty witnesses
- **THEN** the event SHALL be stored in the speaker's memory only
- **AND** no fan-out SHALL occur

### Requirement: publish_event function

The `interface/trigger.lua` module SHALL export `publish_event(event_type, context, witnesses)` which calls `store_event` internally and then publishes to Python via `publisher.send_game_event()` with candidates, world context, and traits.

#### Scenario: Published event includes memory and WS
- **WHEN** `trigger.publish_event(EventType.DEATH, context, witnesses)` is called
- **THEN** the event SHALL be stored in memory (same as store_event)
- **AND** `publisher.send_game_event(event, candidates, world, traits)` SHALL be called

#### Scenario: Candidates list built from speaker and witnesses
- **WHEN** `publish_event` is called with speaker as `context.actor` and 3 witnesses
- **THEN** the candidates list SHALL contain the speaker first, followed by the 3 witnesses

### Requirement: No flags parameter

The `store_event` and `publish_event` functions SHALL NOT accept a `flags` parameter. Events are created with an empty `flags` table `{}`. The old `store_and_publish` function SHALL be removed.

#### Scenario: Event created without flags
- **WHEN** `trigger.store_event(EventType.INJURY, context, witnesses)` is called
- **THEN** the created Event's `flags` field SHALL be `{}`

#### Scenario: Old store_and_publish removed
- **WHEN** code attempts to call `trigger.store_and_publish()`
- **THEN** the function SHALL NOT exist on the trigger module

### Requirement: Old backward-compat functions removed

The `talker_event` and `talker_event_near_player` functions SHALL be removed from `interface/trigger.lua`. All trigger scripts SHALL use `store_event` or `publish_event` directly.

#### Scenario: talker_event_near_player removed
- **WHEN** code attempts to call `trigger.talker_event_near_player()`
- **THEN** the function SHALL NOT exist on the trigger module

### Requirement: Chance utility module

The system SHALL provide `domain/service/chance.lua` exporting a `check(mcm_key)` function. It SHALL read the MCM value via `config.get(mcm_key)` dynamically at call time and return `true` if a random roll (1–100) passes the threshold, `false` otherwise.

#### Scenario: Chance 100 always passes
- **WHEN** `chance.check("triggers/artifact/chance_pickup")` is called and MCM returns 100
- **THEN** it SHALL return `true`

#### Scenario: Chance 0 always fails
- **WHEN** `chance.check("triggers/death/chance_npc")` is called and MCM returns 0
- **THEN** it SHALL return `false`

#### Scenario: Chance 50 uses random roll
- **WHEN** `chance.check("triggers/injury/chance")` is called and MCM returns 50
- **THEN** it SHALL return `true` if `math.random(1, 100) <= 50`, `false` otherwise

#### Scenario: Dynamic MCM read
- **WHEN** player changes MCM chance from 25 to 75 mid-game
- **THEN** the next `chance.check()` call SHALL use 75 (not stale cached value)

### Requirement: Consolidated trigger flow in each script

Each trigger script SHALL follow the consolidated flow:
1. Dynamic `config.get("triggers/<type>/enable")` check — if false, abort entirely
2. Anti-spam/cooldown via `CooldownManager.check()` with mode=0 — if nil, abort; if true, store-only
3. Compute `is_important` from character data (via `importance.is_important_person(flags)`)
4. If `is_important` OR `chance.check("triggers/<type>/chance")` passes → `trigger.publish_event()`
5. Otherwise → `trigger.store_event()`

#### Scenario: Disabled trigger aborts entirely
- **WHEN** `config.get("triggers/death/enable_player")` returns false
- **THEN** the trigger callback SHALL return immediately without creating any event

#### Scenario: Cooldown active stores silently
- **WHEN** enable is true and cooldown is active (check returns true)
- **THEN** the trigger SHALL call `trigger.store_event()` (no dialogue)

#### Scenario: Important event always publishes
- **WHEN** enable is true, cooldown passes (false), and `is_important_person` returns true
- **THEN** the trigger SHALL call `trigger.publish_event()` regardless of chance roll

#### Scenario: Chance roll determines store vs publish
- **WHEN** enable is true, cooldown passes (false), and `is_important` is false
- **THEN** the trigger SHALL call `chance.check("triggers/<type>/chance")`
- **AND** if true → `trigger.publish_event()`
- **AND** if false → `trigger.store_event()`

### Requirement: Dynamic MCM reads in trigger scripts

All trigger scripts SHALL read MCM settings dynamically inside callback functions (not at module scope). No `local mode = mcm.get(...)` at file top level for trigger configuration values.

#### Scenario: MCM change takes effect immediately
- **WHEN** player changes `triggers/death/enable_player` from true to false in MCM
- **THEN** the next death event SHALL be blocked without requiring save/reload

#### Scenario: Cooldown reads dynamic
- **WHEN** player changes `triggers/death/cooldown_player` from 90 to 30 mid-game
- **THEN** new CooldownManager instances or dynamic reads SHALL use the updated value
