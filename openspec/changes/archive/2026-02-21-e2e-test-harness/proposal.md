## Why

The existing integration tests mock at the Python object level (`MockLLMClient`, `MockStateClient`), giving no visibility into the exact JSON payloads that cross the wire to LLM APIs (HTTP) or Lua (ZMQ). Agents writing or debugging tests cannot verify what is actually being sent to external services, making failures hard to diagnose and regressions easy to miss.

## What Changes

- **New e2e test harness** using `zmq.inproc://` transport (no OS socket permissions) and `respx` HTTP interception, both capturing exact wire-level payloads
- **JSON scenario files** as the source of truth for test data — inputs, state mocks, LLM mocks, and expected outputs all in one file per scenario
- **Deep equality assertions** on state queries sent to Lua, HTTP request bodies sent to LLM APIs, and ZMQ messages published back to Lua
- **`ZMQRouter` accepts optional `context` parameter** to allow test fixtures to share a ZMQ context (required for `inproc://`)
- **MCP test runner server** exposing rich tool surface (`list_tests`, `run_tests`, `run_single_test`, `get_test_source`, `get_last_run_results`, `get_captured_payloads`) so agents can run tests without shell permissions
- **`.claude/settings.json`** registering the MCP server in the project

## Capabilities

### New Capabilities

- `e2e-test-harness`: Wire-level e2e test harness using ZMQ inproc + respx, with JSON scenario files, deep equality assertions, and payload capture
- `mcp-test-runner`: MCP server exposing test execution tools for agents without requiring bash permissions

### Modified Capabilities

- `python-zmq-router`: Add optional `context` parameter to `ZMQRouter.__init__` to support shared context for inproc transport in tests

## Impact

- `talker_service/src/talker_service/transport/router.py` — one-line change to accept optional context
- `talker_service/pyproject.toml` — add `respx`, `mcp`, `pytest-json-report` to dev deps
- New: `talker_service/tests/e2e/` — harness, conftest, scenario loader, parametrized runner
- New: `talker_service/tests/e2e/scenarios/` — JSON scenario files (T1–T9 migrated from existing integration tests)
- New: `talker_service/mcp_test_runner.py` — MCP server
- New: `.claude/settings.json` — MCP server registration
