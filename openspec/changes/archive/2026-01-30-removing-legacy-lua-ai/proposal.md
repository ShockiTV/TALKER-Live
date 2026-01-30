## Why

The legacy Lua AI system (HTTP-based LLM calls from within the game engine) is now fully superseded by the Python service architecture. Maintaining two parallel AI processing paths creates confusion, increases code complexity, and the legacy path is untested and likely broken after Phase 2 changes. Removing it simplifies the codebase and makes the Python service the single, required path for AI dialogue.

## What Changes

- **BREAKING**: Remove the legacy Lua AI path entirely - the Python service is now REQUIRED for AI dialogue
- **BREAKING**: Remove MCM options for "Enable Python AI" and "Enable ZMQ" (both always enabled now)
- Remove `bin/lua/infra/AI/` directory and all LLM client implementations (GPT, OpenRouter, Ollama, proxy, requests)
- Remove fallback logic in `talker.lua` that conditionally uses Lua AI when Python is disabled
- Remove HTTP-based LLM calling code from Lua infrastructure
- Update documentation to reflect Python service is mandatory
- Remove or update related tests that mock the legacy Lua AI system
- Clean up `talker_game_load_check.script` references to removed modules

## Capabilities

### New Capabilities

- `python-service-required`: Establishes that the Python service is the sole path for AI processing, with clear error messaging when service is unavailable

### Modified Capabilities

- `lua-zmq-bridge`: Remove optional/fallback behavior - ZMQ is now always required when the mod is active
- `python-dialogue-generator`: Update to be the only dialogue generation path (no fallback considerations)

## Impact

**Code to Remove:**
- `bin/lua/infra/AI/dialogue_cleaner.lua`
- `bin/lua/infra/AI/message_normalizer.lua`
- `bin/lua/infra/AI/requests.lua` (if exists, referenced but may be missing)
- `bin/lua/infra/AI/GPT.lua` (referenced in load check)
- `bin/lua/infra/AI/OpenRouterAI.lua` (referenced in load check)
- `bin/lua/infra/AI/local_ollama.lua` (referenced in load check)
- `bin/lua/infra/AI/proxy.lua` (referenced in load check)
- `bin/lua/infra/AI/transformations.lua` (referenced in load check)
- `bin/lua/infra/AI/prompt_builder.lua` (referenced in load check)

**Code to Modify:**
- `bin/lua/app/talker.lua` - Remove `get_AI_request()` lazy loader, remove legacy AI path, simplify to always use Python service
- `bin/lua/interface/config.lua` - Remove `python_ai_enabled()` getter (or make it always return true)
- `gamedata/scripts/talker_game_load_check.script` - Remove references to deleted AI modules
- `gamedata/scripts/talker_mcm.script` - Remove "Enable Python AI" toggle
- MCM XML files (eng/rus) - Remove Python AI enable strings

**Tests to Update:**
- `tests/app/test_talker.lua` - Remove AI_request mocking, update for new architecture
- `tests/live/test_memory_compression.lua` - Update to use Python service or remove
- `tests/infra/AI/test_dialogue_cleaner.lua` - Remove (tests deleted code)

**Documentation:**
- `AGENTS.md` - Remove "Legacy Lua AI Mode" section
- `docs/Python_Service_Setup.md` - Update to reflect service is mandatory
- `README.md` - Update installation instructions
