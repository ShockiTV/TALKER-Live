## 1. Server Core

- [x] 1.1 Create `mcp_lua_test_runner.py` at project root with MCP server skeleton (Server, stdio_server, tool list, tool dispatch)
- [x] 1.2 Implement lua5.1 discovery (`shutil.which` + hardcoded fallback)
- [x] 1.3 Implement LuaUnit stdout parser (regex for summary line, failure/error capture)
- [x] 1.4 Implement subprocess runner with 30s timeout and cwd set to project root

## 2. Tool Implementations

- [x] 2.1 Implement `list_tests` tool (glob discovery, live/ exclusion, mock/util exclusion)
- [x] 2.2 Implement `run_tests` tool (discover → run each → aggregate → cache to results.json)
- [x] 2.3 Implement `run_single_test` tool (single file execution with full stdout)
- [x] 2.4 Implement `get_last_run_results` tool (read cached `.test_artifacts/lua_last_run/results.json`)

## 3. Registration

- [x] 3.1 Add `lua-tests` server entry to `.vscode/mcp.json`
- [x] 3.2 Add `lua-tests` server entry to `.claude/settings.json`

## 4. Documentation

- [x] 4.1 Update AGENTS.md testing section to reference Lua MCP tools alongside Python MCP tools
- [x] 4.2 Update `openspec/config.yaml` testing section to reference Lua MCP tools
