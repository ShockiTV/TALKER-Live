## Purpose

MCP server that exposes the Lua test suite (LuaUnit-based) as callable tools for AI coding agents. Enables agents to discover, run, and inspect Lua test results without requiring shell access, mirroring the capability of the `talker-tests` MCP server for Python tests.

## Requirements

### Requirement: MCP server entry point

The system SHALL provide `mcp_lua_test_runner.py` at the project root as a standalone MCP server using the `mcp` SDK, launchable via the talker_service venv Python interpreter.

The server SHALL be registered in `.vscode/mcp.json` under `servers.lua-tests` and in `.claude/settings.json` under `mcpServers.lua-tests`, both pointing to the venv Python and the server script.

#### Scenario: Server launches and registers tools

- **WHEN** an MCP-aware editor or agent starts with the config files present
- **THEN** the `lua-tests` MCP server SHALL start automatically
- **AND** the tools `list_tests`, `run_tests`, `run_single_test`, and `get_last_run_results` SHALL be available

### Requirement: Lua interpreter discovery

The server SHALL locate the Lua 5.1 interpreter by:
1. Checking `shutil.which("lua5.1")`
2. Falling back to `C:\Program Files (x86)\LuaRocks\lua5.1.exe`

If neither is found, all tools SHALL return a structured error: `{ "error": "lua5.1 not found on PATH or at default location" }`.

#### Scenario: lua5.1 on PATH

- **WHEN** `lua5.1` is available on the system PATH
- **THEN** the server SHALL use it for all test execution

#### Scenario: lua5.1 at fallback path

- **WHEN** `lua5.1` is NOT on PATH but exists at the hardcoded Windows location
- **THEN** the server SHALL use the fallback location

#### Scenario: lua5.1 not found

- **WHEN** `lua5.1` is not found at either location
- **THEN** all tools SHALL return `{ "error": "lua5.1 not found..." }`

### Requirement: list_tests tool

The system SHALL provide a `list_tests` tool that discovers Lua test files.

Parameters:
- `path` (optional string, default: `"tests/"`) — restrict discovery to a subdirectory
- `include_live` (optional bool, default: `false`) — include `tests/live/` tests

The tool SHALL discover files matching `test_*.lua` recursively under the given path. It SHALL exclude `tests/live/` unless `include_live` is true. It SHALL also exclude `tests/utils/luaunit.lua` and mock files.

Returns: `{ "tests": ["tests/domain/data/test_mutant_names.lua", ...], "count": N }`

#### Scenario: List all tests (excluding live)

- **WHEN** `list_tests()` is called with no arguments
- **THEN** the tool SHALL return all `test_*.lua` files under `tests/` except those in `tests/live/`
- **AND** mock files and utility files SHALL be excluded

#### Scenario: List tests in specific subdirectory

- **WHEN** `list_tests(path="tests/domain/")` is called
- **THEN** only test files under `tests/domain/` SHALL be returned

#### Scenario: Include live tests

- **WHEN** `list_tests(include_live=true)` is called
- **THEN** `tests/live/` test files SHALL also be included in results

### Requirement: run_tests tool

The system SHALL provide a `run_tests` tool that executes Lua test files and returns structured results.

Parameters:
- `path` (optional string, default: `"tests/"`) — restrict to a subdirectory
- `pattern` (optional string) — filter test file names (substring match)
- `include_live` (optional bool, default: `false`) — include live tests
- `fail_fast` (optional bool, default: `false`) — stop after first file with failures

The tool SHALL run each discovered test file as a separate `lua5.1 <file>` subprocess with a 30-second timeout. It SHALL parse LuaUnit stdout for the summary line `Ran N tests in X seconds, Y successes, Z failures`.

Results SHALL be written to `.test_artifacts/lua_last_run/results.json` and returned as:
```json
{
  "passed": N, "failed": N, "errors": N, "duration_s": N,
  "files_run": N, "files_failed": ["tests/path/test_foo.lua"],
  "failures": [{ "file": "...", "output": "..." }],
  "returncode": 0
}
```

#### Scenario: Run all tests

- **WHEN** `run_tests()` is called with no arguments
- **THEN** all test files (excluding `tests/live/`) SHALL be run
- **AND** results SHALL be aggregated across all files into a single summary

#### Scenario: Run with pattern filter

- **WHEN** `run_tests(pattern="serializer")` is called
- **THEN** only test files whose names contain "serializer" SHALL be run

#### Scenario: Fail fast stops after first failing file

- **WHEN** `run_tests(fail_fast=true)` is called and a test file has failures
- **THEN** execution SHALL stop after that file
- **AND** results SHALL reflect only the files run so far

#### Scenario: Test file crashes

- **WHEN** a Lua test file exits with a non-zero code or produces a Lua error
- **THEN** the file SHALL be reported as an error with its stderr/stdout captured
- **AND** execution SHALL continue to the next file (unless fail_fast)

#### Scenario: Test file times out

- **WHEN** a Lua test file does not complete within 30 seconds
- **THEN** the subprocess SHALL be killed
- **AND** the file SHALL be reported as an error with a timeout message

### Requirement: run_single_test tool

The system SHALL provide a `run_single_test` tool that runs one specific Lua test file.

Parameters: `file` (required string, e.g. `"tests/domain/data/test_mutant_names.lua"`)

Returns: same structure as `run_tests` but for a single file, with full stdout included.

#### Scenario: Run single test file

- **WHEN** `run_single_test(file="tests/domain/data/test_mutant_names.lua")` is called
- **THEN** the tool SHALL run that single file with `lua5.1`
- **AND** the full stdout and stderr SHALL be returned alongside structured results

#### Scenario: File not found

- **WHEN** `run_single_test(file="tests/nonexistent.lua")` is called
- **THEN** the tool SHALL return `{ "error": "File not found: tests/nonexistent.lua" }`

### Requirement: get_last_run_results tool

The system SHALL provide a `get_last_run_results` tool that returns cached results from the most recent `run_tests` or `run_single_test` call without re-running tests.

Returns: the results JSON from `.test_artifacts/lua_last_run/results.json`, or `{ "error": "No results found. Run tests first." }` if no run has occurred.

#### Scenario: Returns cached results

- **WHEN** `get_last_run_results()` is called after a previous `run_tests`
- **THEN** the results from the last run SHALL be returned immediately
- **AND** no Lua tests SHALL be re-executed

### Requirement: LuaUnit output parsing

The server SHALL parse LuaUnit's default text output format.

The summary line format is: `Ran N tests in X seconds, Y successes, Z failures`

For failed or errored tests, the server SHALL capture the traceback or error output from stdout/stderr.

#### Scenario: Parse successful run

- **WHEN** LuaUnit output contains `Ran 10 tests in 0.001 seconds, 10 successes, 0 failures`
- **THEN** the parser SHALL report `passed=10, failed=0, errors=0`

#### Scenario: Parse run with failures

- **WHEN** LuaUnit output contains `Ran 8 tests in 0.002 seconds, 7 successes, 1 failure`
- **THEN** the parser SHALL report `passed=7, failed=1, errors=0`

#### Scenario: Parse crashed test

- **WHEN** the subprocess exits non-zero with no summary line (Lua error on load)
- **THEN** the parser SHALL report `errors=1` and capture the error output

### Requirement: Working directory

All Lua test subprocesses SHALL be run with the project root as the current working directory. This ensures `package.path` patterns like `./bin/lua/?.lua` resolve correctly.

#### Scenario: Tests resolve bin/lua modules

- **WHEN** a Lua test file is executed
- **THEN** the subprocess cwd SHALL be the project root directory
- **AND** `require("tests.test_bootstrap")` SHALL find the bootstrap file
