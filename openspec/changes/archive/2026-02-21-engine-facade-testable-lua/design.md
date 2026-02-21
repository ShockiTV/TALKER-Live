## Context

The Lua codebase has a clean architecture (`bin/lua/` with app/domain/infra/interface layers) but 50% of test files fail because modules grab STALKER engine globals at require-time with no fallback. The dependency chain is: `talker_mcm` → `config.lua`/`logger.lua` → everything else. Additionally, `backstories.lua` and `personalities.lua` depend on the engine's `ini_file()` to read `.ltx` config files that contain simple ID lists.

Current state: 8 of 20 test files pass. The failures cascade from 3 root causes: (1) `talker_mcm` has no fallback, (2) `logger.error()` pulls in the full game adapter, (3) `ini_file()` is engine-only. Tests use ad-hoc mocking — some set globals before require, some pre-populate `package.loaded`, some rely on `or require("tests.mocks....")` fallbacks baked into production code.

## Goals / Non-Goals

**Goals:**
- Every `bin/lua/` module can be loaded and tested outside the STALKER engine
- Single mock point for all engine interactions (`mock_engine.lua` replaces 5 separate mocks)
- Standard test bootstrap pattern — one `require` at top of every test file
- Eliminate `ini_file()` dependency by converting .ltx data to Lua tables
- Preserve runtime behavior — no functional changes when running inside the game

**Non-Goals:**
- Migrating `gamedata/scripts/*.script` to use the engine facade (future phase)
- Extracting business logic from trigger/listener scripts into `bin/lua/` (future phase)
- Testing ZMQ bridge (requires LuaJIT FFI — fundamentally untestable in standard Lua 5.1)
- Achieving 100% test coverage — focus is on unblocking, not writing new tests
- Changing the Python service

## Decisions

### 1. Thin Engine Facade at `interface/engine.lua` (Option C from exploration)

**Decision**: Create `interface/engine.lua` as a thin wrapper around engine globals. Keep `game_adapter.lua` as the business-logic layer that imports `engine.lua`.

**Alternatives considered**:
- (A) Engine facade replaces both game_adapter and raw globals — too thick, mixes concerns
- (B) Engine facade replaces raw globals, game_adapter stays but isn't testable — misses the point
- **(C) Chosen**: Engine = thin (raw engine calls), game_adapter = testable business logic importing engine

**Rationale**: `game_adapter.lua` has ~400 lines of real logic (Character creation from game objects, event assembly, near-player filtering). Making `engine.lua` thin means mock_engine is trivial (just stubs), while game_adapter's decision-making becomes directly testable.

### 2. Engine facade exposes a curated API (not a 1:1 mirror of talker_game_queries)

**Decision**: `engine.lua` exposes only what `bin/lua/` modules actually call, organized by domain (time, callbacks, player/NPC state, world, display, files, config). It does NOT mirror the 70+ function talker_game_queries API.

**Rationale**: The mock surface should be minimal and intentional. If `bin/lua/` code doesn't call a function, it doesn't need to be in the facade. New functions are added as needed.

### 3. Lazy binding to globals (not constructor injection)

**Decision**: `engine.lua` references globals lazily (via getter functions) rather than capturing them at module load time.

```lua
-- Lazy: works even if global is set after engine.lua is first required
local function get_queries() return talker_game_queries end

function M.get_name(obj)
    local q = get_queries()
    return q and q.get_name(obj) or "Unknown"
end
```

**Rationale**: STALKER's script loading order is unpredictable. Lazy binding ensures the facade works regardless of when engine globals become available. It also means `require("interface.engine")` never crashes — the module loads fine, and functions return safe defaults when engine is absent (test environment).

### 4. .ltx data converted to Lua tables via auto-generation

**Decision**: Parse `backstories.ltx` and `personalities.ltx` and emit `backstory_data.lua` and `personality_data.lua` as static Lua tables in `domain/repo/`. The .ltx files remain in the repo for reference but are no longer read at runtime.

**Rationale**: The .ltx files contain only comma-separated ID lists per faction section — trivial data. Lua tables are faster (no file I/O), testable (no `ini_file` global), and self-contained.

### 5. Test bootstrap as explicit require (not test runner wrapper)

**Decision**: `tests/test_bootstrap.lua` is required as the first line of every test file.

**Rationale**: Lua's `require` caches modules globally. If test A loads `logger.lua` before globals are set, test B gets the cached broken module. The only reliable approach is setting globals before any module requires, which means bootstrap must run first in each test file. A runner wrapper can't guarantee this because `require` calls in test setup could trigger cascading loads before the wrapper runs.

### 6. MCM defaults extracted to `interface/config_defaults.lua`

**Decision**: The defaults table from `talker_mcm.script` is extracted to a pure Lua module. `interface/config.lua` uses these defaults as fallback values. `mock_engine.lua` uses the same defaults for `get_mcm_value()`.

**Rationale**: Single source of truth for default config values. Tests get realistic defaults without needing the MCM system. Production code falls back gracefully when MCM is unavailable (shouldn't happen in-game, but defensive).

## Risks / Trade-offs

**[Risk] Two paths to engine APIs (facade + direct globals)** → During the transition, `gamedata/scripts/` still uses globals directly while `bin/lua/` uses the facade. This is intentional — script migration is a separate phase. The risk is someone adding new `bin/lua/` code that uses globals instead of the facade. → Mitigation: AGENTS.md / copilot-instructions.md updated to require facade usage.

**[Risk] Facade API drift** → `engine.lua` might not expose a function that new code needs, leading to temptation to use globals. → Mitigation: Adding a function to the facade is trivial (one-liner wrapper). Document the pattern for adding new functions.

**[Risk] Lazy binding performance** → Every engine call goes through an extra function call for the getter. → Mitigation: Negligible. Lua function calls are ~50ns. Game runs at 60fps. Not a concern.

**[Trade-off] .ltx files become stale** → After conversion, the .ltx files in `gamedata/configs/talker/` are no longer the source of truth. → Mitigation: Remove them or add a comment noting they're superseded. The Lua tables are the authoritative source.

**[Trade-off] Existing test mocks become redundant** → `mock_game_queries.lua`, `mock_game_commands.lua`, `mock_game_async.lua` are superseded by `mock_engine.lua`. → Mitigation: Keep them temporarily for any tests that bypass the facade. Remove in a cleanup pass.
