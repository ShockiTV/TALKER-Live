## Why

50% of Lua test files fail because `bin/lua/` modules directly reference STALKER engine globals (`talker_mcm`, `talker_game_queries`, `talker_game_commands`, etc.) at module load time. There is no single abstraction layer — 4 files grab `talker_mcm` with no fallback, 5 files grab `talker_game_queries`, and `logger.lua` (required by everything) cascades into the full engine dependency tree via `game_adapter`. Additionally, backstories and personalities depend on the engine's `ini_file()` to read .ltx config. The result: most business logic in `bin/lua/` is untestable outside the game engine despite having no inherent engine dependency.

## What Changes

- Create `interface/engine.lua` — a single facade module that wraps all STALKER engine globals (`talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, `talker_game_files`) behind a mockable Lua module
- Create `tests/mocks/mock_engine.lua` — test double for the engine facade
- Create `tests/test_bootstrap.lua` — standard bootstrap that every test file requires as its first line, wiring mock_engine and setting globals
- Migrate all `bin/lua/` modules to import `interface.engine` instead of accessing engine globals directly (`config.lua`, `logger.lua`, `game_adapter.lua`, `backstories.lua`, `personalities.lua`, `trigger.lua`, `interface.lua`)
- Convert .ltx config files (`backstories.ltx`, `personalities.ltx`) to in-code Lua tables (`backstory_data.lua`, `personality_data.lua`), eliminating the `ini_file()` engine dependency
- Guard `logger.error()` so it doesn't cascade into `game_adapter` when engine is unavailable
- Fix all currently-failing test files to use the new bootstrap

## Capabilities

### New Capabilities
- `engine-facade`: Thin abstraction module (`interface/engine.lua`) that wraps STALKER engine globals behind a single mockable interface. Covers MCM config access, game queries, game commands, async operations, file paths, and callback registration.
- `lua-test-bootstrap`: Standard test infrastructure (`test_bootstrap.lua` + `mock_engine.lua`) enabling any `bin/lua/` module to be tested outside the game engine with a single require.
- `ltx-to-lua-data`: In-code Lua table replacements for .ltx config files (backstory and personality ID mappings), removing the `ini_file()` engine dependency from domain repositories.

### Modified Capabilities
- `talker-mcm`: MCM defaults will be extracted to a Lua-side table accessible without the engine, so `interface/config.lua` can function in tests.

## Impact

- **bin/lua/** — All modules that currently grab engine globals at load time will be modified to use `require("interface.engine")` instead
- **gamedata/scripts/** — No changes in this phase (scripts continue using globals directly; migration to engine facade is a future phase)
- **tests/** — New bootstrap pattern replaces ad-hoc global-setting in individual test files. Existing mocks (`mock_game_queries`, `mock_game_commands`, `mock_game_async`) become internal to `mock_engine` rather than directly exposed
- **gamedata/configs/talker/*.ltx** — Kept for reference but no longer read at runtime by `bin/lua/` code
- **Test pass rate** — Expected improvement from ~40% to ~90%+ of Lua test files
