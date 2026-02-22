## Why

AI coding agents can run Python tests via the existing `talker-tests` MCP server but have no equivalent tooling for the Lua test suite (~30 test files, ~330 tests). Running Lua tests currently requires shell access and manual `lua5.1` invocations. This asymmetry means agents cannot verify Lua changes without asking the user to run tests manually.

## What Changes

- Create `mcp_lua_test_runner.py` at the project root as a standalone MCP server (mirrors the Python `mcp_test_runner.py` pattern)
- Discover and run Lua tests (`tests/**/test_*.lua`) via `lua5.1` subprocess
- Parse LuaUnit stdout into structured JSON results
- Exclude `tests/live/` by default (these require LLM API keys and cost resources)
- Register the server in `.vscode/mcp.json` and `.claude/settings.json` as `lua-tests`

## Capabilities

### New Capabilities
- `lua-mcp-test-runner`: MCP server exposing Lua test suite as callable tools for AI agents. Provides `list_tests`, `run_tests`, `run_single_test`, and `get_last_run_results` tools. Parses LuaUnit output into structured JSON.

### Modified Capabilities

_(none)_

## Impact

- **New file**: `mcp_lua_test_runner.py` (project root)
- **Modified files**: `.vscode/mcp.json`, `.claude/settings.json` (add `lua-tests` server entry)
- **Dependencies**: Requires `mcp` Python package (already available via the talker_service venv), `lua5.1` on PATH or at known location
- **AGENTS.md**: Testing section should reference Lua MCP tools alongside Python MCP tools
