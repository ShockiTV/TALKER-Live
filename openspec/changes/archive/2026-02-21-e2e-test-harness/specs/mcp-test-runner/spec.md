# mcp-test-runner

## Purpose

MCP server exposing the `talker_service` test suite as callable tools. Agents invoke tools to run tests, inspect results, and retrieve captured wire payloads without requiring bash/shell permissions. The server runs `pytest` as a subprocess with its own OS permissions; agents receive structured data only.

## ADDED Requirements

### Requirement: MCP server entry point

The system SHALL provide `talker_service/mcp_test_runner.py` as a standalone MCP server using the `mcp` SDK, launchable via the venv Python interpreter.

The server SHALL be registered in `.claude/settings.json` under `mcpServers.talker-tests` pointing to the venv Python and the server script.

#### Scenario: Server launches and registers tools

- **WHEN** Claude Code starts with `.claude/settings.json` present
- **THEN** the `talker-tests` MCP server SHALL start automatically
- **AND** all tools SHALL be available to agents in the session

### Requirement: list_tests tool

The system SHALL provide a `list_tests` tool that returns all collectable test node IDs.

Parameters: `path` (optional string, default `"tests/"`)

Returns: `{ "tests": ["tests/e2e/test_scenarios.py::death_wolf_full", ...], "count": N }`

#### Scenario: List all tests

- **WHEN** `list_tests()` is called with no arguments
- **THEN** the tool SHALL run `pytest tests/ --collect-only -q --no-header`
- **AND** SHALL return all node IDs as a JSON array with count

#### Scenario: List tests in specific path

- **WHEN** `list_tests(path="tests/e2e/")` is called
- **THEN** only tests under `tests/e2e/` SHALL be returned

### Requirement: run_tests tool

The system SHALL provide a `run_tests` tool that runs pytest and returns structured results.

Parameters:
- `pattern` (optional string) — passed as `-k` filter
- `path` (optional string, default `"tests/"`)
- `verbose` (optional bool, default `false`)
- `fail_fast` (optional bool, default `false`)

Returns:
```json
{
  "passed": N, "failed": N, "errors": N, "duration_s": N,
  "failures": [{ "node_id": "...", "message": "..." }],
  "returncode": N
}
```

#### Scenario: Run all tests

- **WHEN** `run_tests()` is called
- **THEN** pytest SHALL run against `tests/`
- **AND** results SHALL be returned as structured JSON, not raw stdout

#### Scenario: Run with pattern filter

- **WHEN** `run_tests(pattern="e2e")` is called
- **THEN** pytest SHALL run with `-k e2e`
- **AND** only matching tests SHALL be reported

#### Scenario: Fail fast stops after first failure

- **WHEN** `run_tests(fail_fast=true)` is called
- **THEN** pytest SHALL run with `-x`
- **AND** execution SHALL stop after the first failure

### Requirement: run_single_test tool

The system SHALL provide a `run_single_test` tool that runs one test by exact node ID.

Parameters: `node_id` (required string, e.g. `"tests/e2e/test_scenarios.py::death_wolf_full"`)

Returns: same structure as `run_tests` but for one test, plus `stdout` field with full output.

#### Scenario: Run single test by node ID

- **WHEN** `run_single_test(node_id="tests/e2e/test_scenarios.py::death_wolf_full")` is called
- **THEN** pytest SHALL run exactly that test with `-v --tb=long`
- **AND** the full stdout SHALL be returned alongside structured results

### Requirement: get_test_source tool

The system SHALL provide a `get_test_source` tool that returns the source of a specific test function.

Parameters: `node_id` (required string)

Returns: `{ "node_id": "...", "file": "...", "source": "<function source only, not full file>" }`

#### Scenario: Returns function source only

- **WHEN** `get_test_source(node_id="tests/e2e/test_scenarios.py::TestClass::test_method")` is called
- **THEN** only the source of `test_method` SHALL be returned (not the entire file)
- **AND** the file path SHALL be included for reference

#### Scenario: Returns scenario file for parametrized tests

- **WHEN** `get_test_source` is called for a scenario-parametrized test
- **THEN** the corresponding JSON scenario file content SHALL also be returned under `scenario_file`

### Requirement: get_last_run_results tool

The system SHALL provide a `get_last_run_results` tool that returns the results of the most recent `run_tests` or `run_single_test` call without re-running tests.

Returns: same structure as `run_tests`, with an added `run_at` ISO timestamp. Returns `{ "error": "no results yet" }` if no run has occurred.

#### Scenario: Returns cached results

- **WHEN** `get_last_run_results()` is called after a previous `run_tests`
- **THEN** the results from the last run SHALL be returned immediately
- **AND** pytest SHALL NOT be re-executed

### Requirement: get_captured_payloads tool

The system SHALL provide a `get_captured_payloads` tool that returns the wire-level payloads captured during the last e2e test run.

Parameters: `test_id` (optional string, filter by test name)

Returns:
```json
{
  "test_id": "...",
  "state_queries": [{ "topic": "...", "payload": {} }],
  "http_calls": [{ "url": "...", "body": {} }],
  "zmq_published": [{ "topic": "...", "payload": {} }]
}
```

Source: reads from `.test_artifacts/last_run/payloads.json`. Returns `{ "error": "no artifacts" }` if file does not exist.

#### Scenario: Returns payloads for a specific test

- **WHEN** `get_captured_payloads(test_id="death_wolf_full")` is called
- **THEN** the payload data for that test SHALL be returned from `.test_artifacts/last_run/payloads.json`
- **AND** the agent SHALL see the exact `state_queries`, `http_calls`, and `zmq_published` captured

#### Scenario: Returns all payloads when no test_id given

- **WHEN** `get_captured_payloads()` is called with no arguments
- **THEN** all entries in the payloads file SHALL be returned
