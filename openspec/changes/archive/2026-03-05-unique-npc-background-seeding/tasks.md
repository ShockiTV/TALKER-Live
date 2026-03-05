## 1. Static Data File

- [x] 1.1 Create `bin/lua/domain/data/unique_backgrounds.lua` with ~120 entries keyed by tech_name
- [x] 1.2 Each entry contains: `backstory` (GM-style rewrite), `traits` (3-6 personality adjectives), `connections` (cross-references to other unique NPCs with relationship descriptions)
- [x] 1.3 Backstories rewritten from `texts/backstory/unique.py` in GM briefing style — atmospheric, dramatic, emphasizing personality hooks
- [x] 1.4 Connections parsed from backstory text cross-references AND enriched with STALKER universe knowledge

## 2. Persistence Layer Seeding

- [x] 2.1 Add `seed_unique_backgrounds()` function in `talker_game_persistence.script`
- [x] 2.2 Implement tech_name → game_id resolution: `story_objects.object_id_by_story_id[tech_name]` with alife() fallback scan for MLR NPCs
- [x] 2.3 For each resolved NPC, call `memory_store:mutate()` with verb `set` on `memory.background`
- [x] 2.4 Call `seed_unique_backgrounds()` from `load_state()` when `saved_data.compressed_memories` is nil (brand new save)
- [x] 2.5 Log count of successfully seeded backgrounds

## 3. Tests

- [x] 3.1 Lua unit test: `unique_backgrounds.lua` loads and has expected structure (backstory string, traits table, connections table per entry)
- [x] 3.2 Lua unit test: all connection `id` fields reference valid tech_names from `unique_npcs.lua`
- [x] 3.3 Lua unit test: seeding populates memory_store_v2 backgrounds for resolved NPCs
- [x] 3.4 Lua unit test: seeding skips NPCs whose tech_name can't be resolved to a game_id
- [x] 3.5 Lua unit test: seeding does NOT run when saved_data already contains compressed_memories
- [x] 3.6 Run full Lua test suite and fix any regressions
- [x] 3.7 Run full Python test suite to confirm no regressions
