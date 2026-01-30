## 1. Delete Legacy AI Modules

- [x] 1.1 Delete `bin/lua/infra/AI/dialogue_cleaner.lua`
- [x] 1.2 Delete `bin/lua/infra/AI/message_normalizer.lua`
- [x] 1.3 Delete any other files in `bin/lua/infra/AI/` directory (GPT.lua, OpenRouterAI.lua, local_ollama.lua, proxy.lua, requests.lua, transformations.lua, prompt_builder.lua if they exist)
- [x] 1.4 Remove the empty `bin/lua/infra/AI/` directory

## 2. Simplify talker.lua

- [x] 2.1 Remove `get_AI_request()` lazy loader function
- [x] 2.2 Remove `AI_request` variable and its require
- [x] 2.3 Remove `is_python_ai_enabled()` check function (or make it always return true)
- [x] 2.4 Remove the legacy AI code path in `talker.register_event()` (the else branch after `is_python_ai_enabled()` check)
- [x] 2.5 Remove `talker.generate_dialogue()` function (legacy Lua AI path)
- [x] 2.6 Remove `talker.generate_dialogue_from_instruction()` function (legacy Lua AI path)
- [x] 2.7 Remove `should_someone_speak()` function (moved to Python service)

## 3. Update Configuration Layer

- [x] 3.1 Remove `python_ai_enabled()` getter from `bin/lua/interface/config.lua`
- [x] 3.2 Remove `zmq_enabled()` getter from `bin/lua/interface/config.lua`
- [x] 3.3 Remove `python_ai_enabled` and `zmq_enabled` from `get_all_config()` return table
- [x] 3.4 Update any remaining code that calls these getters to remove the checks

## 4. Update MCM Settings

- [x] 4.1 Remove "Enable Python AI" toggle from `gamedata/scripts/talker_mcm.script`
- [x] 4.2 Remove "Enable ZMQ" toggle from `gamedata/scripts/talker_mcm.script`
- [x] 4.3 Remove related default values from MCM defaults table
- [x] 4.4 Remove Python AI strings from `gamedata/configs/text/eng/talker_mcm.xml`
- [x] 4.5 Remove Python AI strings from `gamedata/configs/text/rus/talker_mcm.xml`
- [x] 4.6 Remove ZMQ enable strings from both MCM XML files

## 5. Update Load Check Script

- [x] 5.1 Remove references to `infra.AI.message_normalizer` from `talker_game_load_check.script`
- [x] 5.2 Remove references to `infra.AI.dialogue_cleaner` from `talker_game_load_check.script`
- [x] 5.3 Remove references to `infra.AI.prompt_builder` from `talker_game_load_check.script`
- [x] 5.4 Remove references to `infra.AI.transformations` from `talker_game_load_check.script`
- [x] 5.5 Remove references to `infra.AI.GPT` from `talker_game_load_check.script`
- [x] 5.6 Remove references to `infra.AI.OpenRouterAI` from `talker_game_load_check.script`
- [x] 5.7 Remove references to `infra.AI.local_ollama` from `talker_game_load_check.script`
- [x] 5.8 Remove references to `infra.AI.proxy` from `talker_game_load_check.script`
- [x] 5.9 Remove references to `infra.AI.requests` from `talker_game_load_check.script`

## 6. Update ZMQ Integration

- [x] 6.1 Update `talker_zmq_integration.script` to always initialize (remove conditional checks)
- [x] 6.2 Add connection status tracking to `bin/lua/infra/zmq/bridge.lua`
- [x] 6.3 Implement HUD notification on first failed dialogue attempt
- [x] 6.4 Implement HUD notification on service recovery
- [x] 6.5 Add HUD message strings to MCM XML files (eng/rus)

## 7. Update Tests

- [x] 7.1 Delete `tests/infra/AI/test_dialogue_cleaner.lua`
- [x] 7.2 Update `tests/app/test_talker.lua` to remove AI_request mocking
- [x] 7.3 Update or delete `tests/live/test_memory_compression.lua` (references legacy AI)
- [x] 7.4 Remove any test directory for deleted AI modules (`tests/infra/AI/` if empty)

## 8. Update Documentation

- [x] 8.1 Remove "Legacy Lua AI Mode" section from `AGENTS.md`
- [x] 8.2 Update `docs/Python_Service_Setup.md` to reflect service is mandatory (not optional)
- [x] 8.3 Update `README.md` installation instructions to emphasize Python service requirement
- [x] 8.4 Update `.github/copilot-instructions.md` to remove legacy AI references

## 9. Finalize

- [x] 9.1 Run Lua tests to verify no regressions: `lua5.1.exe tests/app/test_talker.lua`
- [x] 9.2 Run Python tests to verify no regressions: `cd talker_service; .\.venv\Scripts\activate; python -m pytest tests/ -v`
- [ ] 9.3 Test in-game with Python service running
- [ ] 9.4 Test in-game HUD notification when Python service is not running
- [ ] 9.5 Test in-game recovery notification when Python service reconnects
- [ ] 9.6 Update version number and add BREAKING change to changelog
