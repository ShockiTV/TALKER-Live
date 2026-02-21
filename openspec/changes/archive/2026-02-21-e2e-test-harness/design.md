## Context

The Python service has ~156 tests covering LLM clients, prompt building, dialogue generation, ZMQ routing, and state queries. All tests mock external boundaries at the Python object level — `MockLLMClient` receives `list[Message]`, `MockStateClient` receives method calls. No test ever touches the wire format.

Two external boundaries exist:
1. **LLM APIs** — HTTP via `httpx.AsyncClient`, creating a new client per call in each `complete()` method
2. **Lua/ZMQ** — `ZMQRouter` binds/connects TCP ports (5555/5556), publishing `"{topic} {json}"` strings

The goal is a test harness where the exact serialized bytes that would cross each boundary are captured and deep-asserted against JSON fixture files.

## Goals / Non-Goals

**Goals:**
- Capture exact HTTP request JSON body sent to LLM APIs, assert deep equality
- Capture exact ZMQ wire strings (`"{topic} {json}"`) sent to Lua, assert deep equality
- Assert exact ZMQ queries sent FROM the service TO Lua (state queries)
- JSON scenario files as single source of truth: inputs, mocks, and expected outputs
- No OS socket permissions required — `inproc://` ZMQ transport runs entirely in-process
- MCP server so agents can run tests, list tests, inspect payloads without shell access
- `request_id` (UUID) stripped from state query assertions (Option A — known non-deterministic field)

**Non-Goals:**
- Lua-in-the-loop testing (no actual game, no Lua code executed)
- Testing the ZMQ router's reconnect/timeout logic (covered by existing `test_router.py`)
- Load or performance testing
- Replacing existing unit/integration tests — this layer sits alongside them

## Decisions

### ZMQ: `inproc://` transport with shared context

**Decision**: `ZMQRouter` accepts an optional `context: zmq.asyncio.Context` parameter. When provided, it uses that context instead of creating its own. The test fixture creates one shared context and passes it to both `ZMQRouter` and `LuaSimulator`.

**Why**: ZMQ `inproc://` requires both sockets to share the same `Context` instance. This is an in-process transport — no TCP, no OS socket permissions, no port conflicts. The one-line prod change is minimal and makes the router more composable.

**Alternative considered**: Monkeypatching `ZMQRouter.context` after construction — rejected as fragile and couples tests to internals.

**Alternative considered**: Random free TCP port (`localhost:0`) — works but requires OS socket permission; agents in restricted mode cannot run these tests.

### HTTP: `respx` for httpx interception

**Decision**: Use `respx` to mock httpx at transport level. All LLM clients use `httpx.AsyncClient` directly; `respx` intercepts before any bytes leave the process.

**Why**: `respx` captures the exact serialized request body (`request.content`), the URL, headers, and method — everything needed for deep assertion. It works with `AsyncClient` via `respx.mock` context manager or fixture. The alternative (`unittest.mock.patch`) only intercepts at the Python method level, not the serialized payload.

### Scenario files: single JSON file per scenario

**Decision**: One JSON file per test scenario under `tests/e2e/scenarios/`. Each file contains: `description`, `input`, `state_mocks`, `llm_mocks`, `expected`.

**Why**: Everything about one scenario in one place — agents can generate a new scenario by writing one file. The parametrized test runner (`test_scenarios.py`) discovers and runs all files automatically. Splitting into per-field files (e.g., `memory_response.json` separately) increases file count without benefit; the scenario file stays manageable.

**`request_id` handling (Option A)**: Before asserting state queries, strip `request_id` from actual payload. The harness already uses `request_id` internally for response correlation — tests don't need to see it.

### Payload capture: in-memory, written to `.test_artifacts/` after each test

**Decision**: `LuaSimulator` and respx call recorder accumulate payloads in-memory during the test. After settlement, payloads are serialized to `.test_artifacts/last_run/payloads.json` (keyed by test node ID). The MCP server reads from this file for `get_captured_payloads`.

**Why**: Decouples the test harness from the MCP server — no shared state, just a file. The MCP server does not need to import pytest or any test code.

### MCP server: subprocess-based, project-local

**Decision**: `talker_service/mcp_test_runner.py` using the `mcp` SDK, registered in `.claude/settings.json` pointing at the venv Python. Exposes: `list_tests`, `run_tests`, `run_single_test`, `get_test_source`, `get_last_run_results`, `get_captured_payloads`.

**Why**: Agents call MCP tools instead of shell commands. The server runs `pytest` as a subprocess with its own permissions — the agent gets structured results, not raw shell access. `pytest-json-report` provides machine-readable output without parsing stdout.

### Test settlement: `asyncio.Event` + timeout

**Decision**: After publishing the input ZMQ message, the harness waits for an `asyncio.Event` that fires when `dialogue.display` is published (or a configurable timeout). This is cleaner than `asyncio.sleep` polling.

**Why**: `dialogue.display` is the terminal event of the lifecycle — once it's published, all upstream work (state queries, LLM calls) has completed. Avoids arbitrary sleeps and makes tests deterministic.

## Risks / Trade-offs

- **`inproc://` bind order**: ZMQ `inproc://` requires the bind to happen before connect. The `LuaSimulator` must bind before `ZMQRouter` connects. The harness fixture controls startup order, but this must be documented.
- **`LuaSimulator` state.response routing**: The simulator must echo back `request_id` from the query into the response — if it doesn't, `StateQueryClient` futures never resolve. The simulator receives the query wire string, parses it, looks up the mock response by topic, injects `request_id`, and publishes `state.response`.
- **respx scope**: `respx.mock` must be active for the full duration of the async test. Using it as a pytest fixture (not context manager) avoids accidentally missing calls made before the mock is active.
- **LLM mock ordering**: `llm_mocks` is an ordered list — first HTTP call gets first mock. If the service makes calls in a different order than expected, mocks silently return wrong responses. Tests should assert call count matches `len(llm_mocks)`.
- **Windows asyncio**: The service uses `asyncio.ProactorEventLoop` on Windows (set in `run.py`). Tests must use `pytest-asyncio` with `asyncio_mode = "auto"` and the same loop policy.

## Decisions (continued)

### get_test_source returns function source only

`get_test_source` SHALL return the source of the specific test function extracted via `ast`, not the full file. Full files contain large JSON constants and fixture boilerplate that add noise without value for an agent inspecting one test.

### Scenario input: structured objects, not raw wire strings

`input` in scenario files uses `{ "topic": "game.event", "payload": { ... } }` — structured JSON, not a pre-serialized wire string. The harness serializes to `"{topic} {json}"` before publishing over the inproc socket. This keeps scenario files readable and editable without dealing with double-escaped strings.

The same applies throughout: `expected.zmq_published` uses `{ topic, payload }` objects (already the case). `expected.state_queries` uses `{ topic, payload }` objects with `request_id` stripped (Option A). No field in any scenario file contains a raw `"{topic} {json}"` wire string — that is always an implementation detail of the harness.
