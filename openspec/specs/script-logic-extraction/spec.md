# script-logic-extraction

## Purpose

Requirements for extracting pure business logic from `gamedata/scripts/` into testable `bin/lua/` modules. Scripts become thin engine adapters; domain logic lives in testable modules.

## Requirements

### Requirement: Scripts delegate pure logic to bin/lua modules

All trigger scripts and `talker_game_queries.script` SHALL delegate pure business logic to the corresponding `bin/lua/` modules. The scripts SHALL retain only engine API calls, callback registration, and wiring code.

#### Scenario: talker_game_queries delegates describe_mutant
- **WHEN** `talker_game_queries.describe_mutant(obj)` is called
- **THEN** it resolves the technical name via engine API
- **AND** delegates name matching to `domain.data.mutant_names.describe(tech_name)`

#### Scenario: talker_game_queries delegates get_rank_value
- **WHEN** `talker_game_queries.get_rank_value(name)` is called
- **THEN** it delegates to `domain.data.ranks.get_value(name)`

#### Scenario: talker_game_queries delegates get_reputation_tier
- **WHEN** `talker_game_queries.get_reputation_tier(value)` is called
- **THEN** it delegates to `domain.data.ranks.get_reputation_tier(value)`

#### Scenario: talker_game_queries delegates describe_world
- **WHEN** `talker_game_queries.describe_world(speaker, listener)` is called
- **THEN** it fetches engine data (weather, rain, hour, location)
- **AND** delegates string assembly to `interface.world_description.build_description(params)`

#### Scenario: talker_game_queries delegates get_character_event_info
- **WHEN** `talker_game_queries.get_character_event_info(char)` is called
- **THEN** it delegates formatting to `domain.data.ranks` or character formatting module

#### Scenario: talker_game_queries delegates is_unique_character_by_id
- **WHEN** `talker_game_queries.is_unique_character_by_id(npc_id)` is called
- **THEN** it uses `domain.data.unique_npcs` for the set lookup
- **AND** retains the engine fallback (`alife():object()` for story_id resolution)

### Requirement: Trigger scripts delegate cooldown to CooldownManager

Trigger scripts with `get_silence_status()` functions SHALL replace inline cooldown logic with `domain.service.cooldown` CooldownManager instances. The calling convention (return values) SHALL remain unchanged for each script.

#### Scenario: Death trigger uses CooldownManager
- **WHEN** `talker_trigger_death.script` checks cooldown
- **THEN** it uses a CooldownManager with slots "player" and "npc"
- **AND** the behavior matches the original (returns `true` on cooldown, not `nil`)

#### Scenario: Artifact trigger uses CooldownManager
- **WHEN** `talker_trigger_artifact.script` checks cooldown
- **THEN** it uses a CooldownManager with anti-spam and slots "pickup", "use", "equip"
- **AND** the behavior matches the original (returns `nil` on anti-spam, `true` on cooldown)

#### Scenario: Injury trigger uses CooldownManager
- **WHEN** `talker_trigger_injury.script` checks cooldown
- **THEN** it uses a CooldownManager with `on_cooldown = "abort"`
- **AND** the behavior matches the original (returns `nil` on cooldown)

#### Scenario: Task trigger uses CooldownManager
- **WHEN** `talker_trigger_task.script` checks cooldown
- **THEN** it uses a CooldownManager with anti-spam
- **AND** the behavior matches the original

#### Scenario: Anomalies trigger uses CooldownManager
- **WHEN** `talker_trigger_anomalies.script` checks cooldown
- **THEN** it uses a CooldownManager with anti-spam and slots "damage", "proximity"
- **AND** the behavior matches the original

### Requirement: ZMQ query handlers delegate serialization

`talker_zmq_query_handlers.script` SHALL use `infra.zmq.serializer` instead of inline serialization functions.

#### Scenario: Query handler uses serializer module
- **WHEN** a state query response is built
- **THEN** it calls `serializer.serialize_event(event)` instead of the local `serialize_event` function
- **AND** `serializer.serialize_character(char)` instead of the local `serialize_character` function

#### Scenario: Wire format unchanged
- **WHEN** the query handler builds a response using the serializer module
- **THEN** the JSON output is byte-identical to the previous inline serialization

### Requirement: Utility functions replaced with framework/utils

Scripts that define utility functions (`must_exist`, `try`, `join_tables`, `Set`, `shuffle`, `safely`) SHALL replace them with `require("framework.utils")` calls.

#### Scenario: talker_game_queries uses utils module
- **WHEN** `talker_game_queries.script` needs `must_exist` or `Set`
- **THEN** it uses `utils.must_exist()` and `utils.Set()` from `framework/utils.lua`
- **AND** the local definitions are removed

### Requirement: Death trigger delegates importance check

`talker_trigger_death.script` SHALL delegate the `is_important_person` logic to a domain module (`domain/service/importance.lua`). The caller resolves engine data and passes pure values.

#### Scenario: Importance check with pure data
- **WHEN** a death event occurs
- **THEN** the death trigger resolves `is_player`, `is_companion`, `is_unique`, `rank` from engine
- **AND** passes these as flags to `importance.is_important_person(flags)`
- **AND** the importance module makes the decision without engine calls

#### Scenario: Player kill is important
- **WHEN** `is_important_person({ is_player = true })` is called
- **THEN** it returns `true`

#### Scenario: Companion kill is important
- **WHEN** `is_important_person({ is_companion = true })` is called
- **THEN** it returns `true`

#### Scenario: Unique NPC is important
- **WHEN** `is_important_person({ is_unique = true })` is called
- **THEN** it returns `true`

#### Scenario: High rank is important
- **WHEN** `is_important_person({ rank = "master" })` is called
- **THEN** it returns `true`

#### Scenario: Random low-rank NPC is not important
- **WHEN** `is_important_person({ is_player = false, is_companion = false, is_unique = false, rank = "novice" })` is called
- **THEN** it returns `false`

### Requirement: No behavioral changes

After script refactoring, the observable behavior SHALL be identical. Events SHALL be created with the same data, cooldowns SHALL trigger at the same thresholds, and ZMQ messages SHALL have the same wire format.

#### Scenario: Death event unchanged
- **WHEN** a creature dies near the player in-game
- **THEN** the same event data is produced as before refactoring

#### Scenario: Cooldown timing unchanged
- **WHEN** events occur at the same timestamps as before refactoring
- **THEN** the same events are silent/spoken/aborted as before
