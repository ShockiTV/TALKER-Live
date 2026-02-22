## Context

The project has an existing Python MCP test runner (`talker_service/mcp_test_runner.py`) that exposes pytest as MCP tools. The Lua test suite (~30 files, ~330 tests) uses LuaUnit and runs via `lua5.1 tests/<path>/test_*.lua` but has no MCP tooling — agents must ask the user to run tests manually.

The Lua executable lives at `C:\Program Files (x86)\LuaRocks\lua5.1.exe` and is on PATH as `lua5.1` after PATH setup. LuaUnit outputs a final summary line: `Ran N tests in X seconds, Y successes, Z failures`.

`tests/live/` contains tests that require actual LLM API keys and should be excluded by default.

## Goals / Non-Goals

**Goals:**
- Give AI agents the same test-running capability for Lua as they have for Python
- Parse LuaUnit stdout into structured JSON results
- Exclude expensive live tests by default
- Mirror the Python MCP server's tool surface where applicable

**Non-Goals:**
- LuaUnit XML/JUnit output parsing (text is sufficient)
- Code coverage measurement
- Lua LSP or type-checking integration
- CI/GitHub Actions integration (deferred)

## Decisions

### 1. Python MCP server (not Lua)

Write the server in Python using the `mcp` SDK, identical to the Python test runner. Lua has no MCP server library, and Python provides natural subprocess management, JSON handling, and async.

### 2. Project root location

Place `mcp_lua_test_runner.py` at the project root (not inside `talker_service/`) because Lua tests live at the project root under `tests/`. The Python runner lives inside `talker_service/` because its tests are there.

### 3. lua5.1 discovery

Use `shutil.which("lua5.1")` to find the interpreter. If not found, fall back to a hardcoded Windows path (`C:\Program Files (x86)\LuaRocks\lua5.1.exe`). If neither works, tools return an error message.

### 4. LuaUnit stdout parsing

Parse the summary line `Ran N tests in X seconds, Y successes, Z failures` with regex. Capture individual test results from lines matching `^(OK|FAIL|ERROR):\s+(.+)` patterns. For errors/failures, capture the full LuaUnit traceback block.

### 5. No `get_captured_payloads` / `get_test_source` tools

Unlike the Python runner, Lua tests don't produce wire-level artifacts and LuaUnit doesn't have parametrized scenarios. Drop these two tools. Keep: `list_tests`, `run_tests`, `run_single_test`, `get_last_run_results`.

### 6. Exclude `tests/live/` by default

The `list_tests` and `run_tests` tools SHALL skip `tests/live/` unless explicitly requested via `include_live=true`. This avoids accidental resource consumption.

### 7. Results caching

Write last run results to `.test_artifacts/lua_last_run/results.json` (parallel to the Python runner's `.test_artifacts/last_run/`).

### 8. Server name: `lua-tests`

Registered in config files as `lua-tests` (vs `talker-tests` for Python).

## Risks / Trade-offs

- **[LuaUnit output changes]** → Regex parsing is fragile. Mitigation: LuaUnit version is pinned (bundled in `tests/utils/luaunit.lua`), so output format won't change unexpectedly.
- **[lua5.1 not on PATH]** → Mitigation: fallback to hardcoded path + clear error message if not found.
- **[test_mic.lua crash]** → One test file crashes on load (missing module). Mitigation: subprocess timeout + error capture. The crash is reported as a test error, not an MCP server crash.
- **[Subprocess timeout]** → Individual test files could hang. Mitigation: 30-second subprocess timeout matching the Python runner.
