## Why

The `engine-facade-testable-lua` change makes `bin/lua/` modules testable by wrapping engine globals behind a mockable facade. But ~5,200 lines of `gamedata/scripts/` still contain ~100 functions with extractable business logic (33 pure, 67 mixed) buried alongside engine glue code. This logic — cooldown timers, data lookups, serialization, importance classification — is duplicated across scripts and completely untestable. Extracting it into `bin/lua/` modules makes it testable, reduces duplication, and completes the clean architecture migration.

## What Changes

- Extract **pure utility functions** scattered across scripts (`must_exist`, `try`, `join_tables`, `Set`, `shuffle`, `safely`) into `framework/utils.lua`
- Extract **domain data tables** from `talker_game_queries.script` (important_npcs set, mutant name patterns, rank value map, reputation tiers) into dedicated `domain/data/` modules
- Extract a **generic CooldownManager** from 6 trigger scripts that each implement near-identical cooldown logic (anti-spam timer + dialogue cooldown + silence mode)
- Extract **ZMQ serialization** functions (`serialize_character`, `serialize_context`, `serialize_event`, `serialize_events`) from `talker_zmq_query_handlers.script` into `infra/zmq/serializer.lua`
- Extract **world description builder** — separate the pure string assembly in `describe_world()` from the engine data fetching
- Extract **character event info** and **importance classification** logic into domain modules
- **Thin out `talker_game_queries.script`** by delegating pure logic to new `bin/lua/` modules while keeping engine-only calls in the script
- Refactor **trigger scripts** to delegate business logic to domain services, keeping only engine callbacks and event wiring in the `.script` files

## Capabilities

### New Capabilities
- `framework-utils`: Common utility functions (`must_exist`, `try`, `join_tables`, `Set`, `shuffle`, `safely`, `array_iter`) extracted from scripts into `framework/utils.lua`
- `domain-data-tables`: Pure Lua data modules for NPC data (`unique_npcs`), mutant names, rank values, and reputation tiers — currently embedded in `talker_game_queries.script`
- `cooldown-manager`: Generic cooldown service replacing duplicated timer logic across 6+ trigger scripts (death, injury, artifact, anomalies, task, emission)
- `zmq-serializer`: ZMQ wire-format serialization for Character, Event, and Context objects, extracted from `talker_zmq_query_handlers.script`
- `world-description-builder`: Pure string assembly for world descriptions (time-of-day, weather, shelter, campfire), split from engine data fetching in `talker_game_queries.script`
- `script-logic-extraction`: Refactoring of trigger scripts and `talker_game_queries.script` to delegate business logic to the new `bin/lua/` modules

### Modified Capabilities
- `lua-state-query-handler`: The query handler will import `infra/zmq/serializer.lua` instead of defining serialization inline
- `lua-event-creation`: Trigger scripts will delegate importance/cooldown logic to domain services rather than implementing them inline

## Impact

- **`gamedata/scripts/talker_game_queries.script`** (~992 lines) — largest change; ~300 lines of pure data/logic extracted, script becomes a thin engine adapter delegating to domain modules
- **`gamedata/scripts/talker_trigger_*.script`** (12 files) — cooldown logic replaced with `CooldownManager`, importance checks delegated to domain service
- **`gamedata/scripts/talker_zmq_query_handlers.script`** (~629 lines) — serialization extracted to `infra/zmq/serializer.lua`
- **`bin/lua/framework/`** — new `utils.lua` module
- **`bin/lua/domain/data/`** — new directory with `unique_npcs.lua`, `mutant_names.lua`, `ranks.lua`
- **`bin/lua/domain/service/`** — new directory with `cooldown.lua`, `importance.lua`
- **`bin/lua/infra/zmq/`** — new `serializer.lua`
- **`bin/lua/interface/`** — new `world_description.lua`
- **Test coverage** — all extracted modules get dedicated test files
- **No Python changes** — wire protocol and message formats are unchanged
