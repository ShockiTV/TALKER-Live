## 1. Framework Utilities (zero dependencies)

- [x] 1.1 Create `bin/lua/framework/utils.lua` with `must_exist`, `try`, `join_tables`, `Set`, `shuffle`, `safely`, `array_iter`
- [x] 1.2 Create `tests/utils/test_utils.lua` with tests for all 7 functions
- [x] 1.3 Run tests and verify all pass

## 2. Domain Data Tables (zero dependencies)

- [x] 2.1 Create `bin/lua/domain/data/unique_npcs.lua` — extract `important_npcs` Set from `talker_game_queries.script` (~120 story IDs)
- [x] 2.2 Create `bin/lua/domain/data/mutant_names.lua` — extract `patternToNameMap` + `describe(tech_name)` from `describe_mutant()`
- [x] 2.3 Create `bin/lua/domain/data/ranks.lua` — extract `get_value(rank_name)` from `get_rank_value()` and `get_reputation_tier(rep_value)` from `get_reputation_tier()`
- [x] 2.4 Extract `get_character_event_info(char)` as a pure formatting function (to `domain/data/ranks.lua` or `domain/model/character.lua`)
- [x] 2.5 Create `tests/domain/data/test_unique_npcs.lua` — verify known NPCs are in set, unknown are not
- [x] 2.6 Create `tests/domain/data/test_mutant_names.lua` — verify pattern matching (pseudodog vs dog, known vs unknown)
- [x] 2.7 Create `tests/domain/data/test_ranks.lua` — verify rank values, reputation tiers, edge cases (nil, non-number)
- [x] 2.8 Run all data table tests and verify all pass

## 3. Cooldown Manager (depends on nothing)

- [x] 3.1 Create `bin/lua/domain/service/cooldown.lua` — CooldownManager class with `new(config)` and `check(slot, time, mode)`
- [x] 3.2 Support named timer slots, optional anti-spam layer, configurable `on_cooldown` behavior ("silent" vs "abort")
- [x] 3.3 Create `tests/domain/service/test_cooldown.lua` — test single timer, multi-slot, anti-spam, mode handling, on_cooldown behavior
- [x] 3.4 Verify test coverage matches all 5 trigger cooldown patterns (death, injury, artifact, anomalies, task)
- [x] 3.5 Run cooldown tests and verify all pass

## 4. Importance Service (depends on unique_npcs, ranks)

- [x] 4.1 Create `bin/lua/domain/service/importance.lua` — `is_important_person(flags)` pure predicate
- [x] 4.2 Create `tests/domain/service/test_importance.lua` — test player, companion, unique, high-rank, low-rank scenarios
- [x] 4.3 Run importance tests and verify all pass

## 5. ZMQ Serializer (depends on nothing)

- [x] 5.1 Create `bin/lua/infra/zmq/serializer.lua` — `serialize_character`, `serialize_context`, `serialize_event`, `serialize_events`
- [x] 5.2 Create `tests/infra/zmq/test_serializer.lua` — verify field mapping, nil handling, character key recognition, companions array
- [x] 5.3 Run serializer tests and verify all pass

## 6. World Description Builder (depends on nothing)

- [x] 6.1 Create `bin/lua/interface/world_description.lua` — `build_description(params)`, `time_of_day(hour)`, `describe_emission(flags)`, `describe_weather(str, emission)`, `describe_shelter(rain, exposure)`
- [x] 6.2 Create `tests/interface/test_world_description.lua` — test full descriptions, edge cases, all time periods, shelter logic
- [x] 6.3 Run world description tests and verify all pass

## 7. Refactor talker_game_queries.script

- [x] 7.1 Add `require` calls for `framework.utils`, `domain.data.unique_npcs`, `domain.data.mutant_names`, `domain.data.ranks`, `interface.world_description`
- [x] 7.2 Replace `must_exist`, `try`, `join_tables`, `Set` definitions with `utils.*` calls
- [x] 7.3 Replace `important_npcs` inline data with `require("domain.data.unique_npcs")`
- [x] 7.4 Replace `patternToNameMap` logic in `describe_mutant()` with `mutant_names.describe(tech_name)` delegation
- [x] 7.5 Replace `get_rank_value()` and `get_reputation_tier()` bodies with delegation to `ranks.*`
- [x] 7.6 Replace `get_character_event_info()` body with delegation to extracted module
- [x] 7.7 Replace `describe_current_time()`, `describe_emission()`, `describe_weather()`, `describe_shelter()`, `describe_world()` with delegation to `world_description.*` (keep engine data fetching in script)
- [x] 7.8 Verify `is_unique_character_by_id()` uses `unique_npcs` for set lookup while retaining engine fallback

## 8. Refactor Trigger Scripts (cooldown delegation)

- [x] 8.1 Refactor `talker_trigger_death.script` — replace `get_silence_status` with CooldownManager (slots "player"/"npc", no anti-spam, on_cooldown="silent")
- [x] 8.2 Refactor `talker_trigger_injury.script` — replace with CooldownManager (single slot, no anti-spam, on_cooldown="abort")
- [x] 8.3 Refactor `talker_trigger_artifact.script` — replace with CooldownManager (slots "pickup"/"use"/"equip", with anti-spam)
- [x] 8.4 Refactor `talker_trigger_anomalies.script` — replace with CooldownManager (slots "damage"/"proximity", with anti-spam)
- [x] 8.5 Refactor `talker_trigger_task.script` — replace with CooldownManager (single slot, with anti-spam)
- [x] 8.6 Extract `is_important_person` from death trigger → delegate to `importance.is_important_person(flags)`

## 9. Refactor ZMQ Query Handlers (serialization delegation)

- [x] 9.1 Add `require("infra.zmq.serializer")` to `talker_zmq_query_handlers.script`
- [x] 9.2 Replace inline `serialize_character`, `serialize_context`, `serialize_event`, `serialize_events` with `serializer.*` calls
- [x] 9.3 Remove the 4 local serialization function definitions
- [x] 9.4 Verify no wire format changes (compare ZMQ output before/after if possible)

## 10. Verification and Cleanup

- [x] 10.1 Run all new Lua tests (utils, data tables, cooldown, importance, serializer, world description) — verify all pass
- [x] 10.2 Run all existing Lua tests — verify no regressions
- [x] 10.3 Grep `gamedata/scripts/` for any remaining inline definitions of extracted functions (must_exist, try, join_tables, etc.) — remove duplicates
- [x] 10.4 Grep `talker_game_queries.script` for any remaining `patternToNameMap`, `important_npcs`, `ranks_map` — verify removed
- [x] 10.5 Update AGENTS.md to document new module locations and extraction pattern
