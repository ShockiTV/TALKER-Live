## 1. Extract MCM Defaults

- [x] 1.1 Create `bin/lua/interface/config_defaults.lua` with all MCM default values as a plain Lua table (no engine dependencies)
- [x] 1.2 Audit `talker_mcm.script` and `interface/config.lua` to ensure every MCM key has a default in the new module
- [x] 1.3 Update `interface/config.lua` to require `config_defaults` and use it as fallback when MCM returns nil

## 2. Create Engine Facade

- [x] 2.1 Create `bin/lua/interface/engine.lua` with lazy-binding getters for all engine globals (`talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, `talker_game_files`, `printf`, `ini_file`, `CreateTimeEvent`, `ResetTimeEvent`, `RegisterScriptCallback`)
- [x] 2.2 Implement MCM section: `engine.get_mcm_value(key)` delegating to `talker_mcm.get(key)`
- [x] 2.3 Implement game queries section: wrapper functions for all `talker_game_queries` calls used by `bin/lua/` (get_name, get_id, is_alive, get_faction, get_rank, is_player, is_stalker, is_companion, is_in_combat, are_enemies, get_relations, get_player, is_player_alive, get_player_weapon, get_weapon, get_nearby_characters, get_companions, get_position, get_obj_by_id, get_technical_name, get_technical_name_by_id, is_unique_character_by_id, get_unique_character_personality, get_location_name, get_location_technical_name, get_game_time_ms, iterate_nearest, is_living_character, get_distance_between, load_xml, load_random_xml, describe_mutant, describe_world, describe_current_time, get_enemies_fighting_player, is_psy_storm_ongoing, is_surge_ongoing, get_community_goodwill, get_community_relation, get_real_player_faction, get_rank_value, get_reputation_tier, get_story_id, get_character_event_info)
- [x] 2.4 Implement game commands section: `display_message`, `display_hud_message`, `send_news_tip`, `play_sound`, `SendScriptCallback`
- [x] 2.5 Implement async/files section: `repeat_until_true`, `get_base_path`
- [x] 2.6 Implement time events and callbacks: `create_time_event`, `reset_time_event`, `register_callback`
- [x] 2.7 Verify `require("interface.engine")` loads without error when all globals are nil

## 3. Convert .ltx Data to Lua Tables

- [x] 3.1 Write a one-shot Lua (or Python) script to parse `gamedata/configs/talker/backstories.ltx` and emit `bin/lua/domain/repo/backstory_data.lua`
- [x] 3.2 Write a one-shot script to parse `gamedata/configs/talker/personalities.ltx` and emit `bin/lua/domain/repo/personality_data.lua`
- [x] 3.3 Verify generated tables match .ltx contents exactly (faction keys, ID types, ID counts)
- [x] 3.4 Update `domain/repo/backstories.lua` to `require("domain.repo.backstory_data")` instead of `ini_file("talker\\backstories.ltx")`; remove `ini_file` usage
- [x] 3.5 Update `domain/repo/personalities.lua` to `require("domain.repo.personality_data")` instead of `ini_file("talker\\personalities.ltx")`; remove `ini_file` usage

## 4. Migrate bin/lua Modules to Engine Facade

- [x] 4.1 Migrate `interface/config.lua`: replace `talker_mcm.get(key)` calls with `engine.get_mcm_value(key)`, use `config_defaults` fallback
- [x] 4.2 Migrate `framework/logger.lua`: replace `talker_mcm` access with `engine.get_mcm_value()`; guard `logger.error()` display-to-player so it does not cascade into game_adapter (pcall or conditional require)
- [x] 4.3 Migrate `infra/game_adapter.lua`: replace direct `talker_game_queries`, `talker_game_commands`, `talker_game_async` access with `engine.*` calls
- [x] 4.4 Migrate `domain/repo/backstories.lua`: replace `talker_game_queries` and `talker_mcm` access with `engine.*` calls (already handled ini_file in step 3.4)
- [x] 4.5 Migrate `domain/repo/personalities.lua`: replace `talker_game_queries` and `talker_mcm` access with `engine.*` calls (already handled ini_file in step 3.5)
- [x] 4.6 Migrate `interface/trigger.lua`: replace any direct engine global usage with facade calls
- [x] 4.7 Migrate `interface/interface.lua`: replace any direct engine global usage with facade calls
- [x] 4.8 Migrate `infra/file_io.lua`: replace `talker_game_files` access with `engine.get_base_path()`
- [x] 4.9 Migrate any remaining `bin/lua/` files that reference engine globals directly
- [x] 4.10 Grep `bin/lua/` for any remaining direct references to `talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, `talker_game_files`, `ini_file`; fix any found

## 5. Create Test Infrastructure

- [x] 5.1 Create `tests/mocks/mock_engine.lua` implementing the full `interface/engine.lua` API with test-friendly stubs and MCM defaults from `config_defaults`
- [x] 5.2 Add injectable test data API to mock_engine (e.g., `_set(key, value)` to override return values per test)
- [x] 5.3 Create `tests/test_bootstrap.lua`: sets package.path, injects `mock_engine` into `package.loaded["interface.engine"]`, sets engine globals (`talker_mcm`, `printf`, etc.) to safe stubs
- [x] 5.4 Verify bootstrap is idempotent (multiple requires do not error or re-run setup)

## 6. Update Existing Tests

- [x] 6.1 Add `require("tests.test_bootstrap")` as first line (after package.path) to all test files that currently fail due to missing engine globals
- [x] 6.2 Add bootstrap to currently passing tests that use ad-hoc mocking (unify pattern)
- [x] 6.3 Update `tests/mocks/mock_characters.lua` to work with bootstrap (Character.new should resolve backstory/personality via mock_engine)
- [x] 6.4 Run all 20 test files; verify previously passing tests still pass
- [x] 6.5 Run all 20 test files; verify previously failing tests now pass
- [x] 6.6 Fix any remaining test failures discovered during verification

## 7. Documentation and Cleanup

- [x] 7.1 Update AGENTS.md to document engine facade usage requirement for `bin/lua/` code
- [x] 7.2 Update `.github/copilot-instructions.md` to reference engine facade pattern
- [x] 7.3 Add comments to .ltx files noting they are superseded by Lua data tables
- [x] 7.4 Remove or deprecate old mock files (`mock_game_queries.lua`, `mock_game_commands.lua`, `mock_game_async.lua`) once all tests use mock_engine
