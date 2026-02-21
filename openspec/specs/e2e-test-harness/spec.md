# e2e-test-harness

## Purpose

Wire-level e2e test harness for the Python service. Uses `zmq.inproc://` transport and `respx` HTTP interception to capture exact serialized payloads on both external boundaries (ZMQ to Lua, HTTP to LLM APIs). JSON scenario files define all inputs, mocks, and expected outputs. Assertions are deep equality on deserialized JSON objects.

## Requirements

### Requirement: LuaSimulator fixture

The system SHALL provide a `LuaSimulator` class that simulates the Lua side of the ZMQ bridge within the same process, using `inproc://` transport with a shared `zmq.asyncio.Context`.

The `LuaSimulator` SHALL:
- Bind a PUB socket on `inproc://lua-to-python` (simulating Lua's PUB on port 5555)
- Connect a SUB socket to `inproc://python-to-lua` (simulating Lua's SUB on port 5556)
- Subscribe to all topics on the SUB socket
- Record all received messages as raw wire strings (`"{topic} {json}"`)
- Accept `state_mocks` dict keyed by topic, mapping to configured response data
- When a `state.query.*` message is received, parse the `request_id` from the payload, look up the mock response by topic, inject `request_id`, and publish `state.response {json}` back
- Expose `published_to_service: list[str]` (what the simulator sent to Python)
- Expose `received_from_service: list[str]` (what the simulator received from Python)
- Expose a `done_event: asyncio.Event` that fires when `dialogue.display` is received

#### Scenario: LuaSimulator publishes event to service

- **WHEN** `lua_sim.publish(topic, payload_dict)` is called
- **THEN** the harness SHALL serialize to `"{topic} {json}"` wire format internally
- **AND** the message SHALL be sent over `inproc://lua-to-python`
- **AND** the `ZMQRouter` SUB socket SHALL receive it
- **AND** scenario files SHALL never contain raw wire strings — only structured `{ topic, payload }` objects

#### Scenario: LuaSimulator responds to state query

- **WHEN** the service publishes `"state.query.memories {\"request_id\": \"abc\", \"character_id\": \"12345\"}"`
- **THEN** `LuaSimulator` SHALL receive the message on its SUB socket
- **AND** SHALL look up the mock for topic `"state.query.memories"`
- **AND** SHALL publish `"state.response {\"request_id\": \"abc\", \"data\": {<mock_response>}}"` back
- **AND** the query SHALL be recorded in `received_from_service`

#### Scenario: LuaSimulator fires done_event on dialogue.display

- **WHEN** the service publishes `"dialogue.display {...}"` to Lua
- **THEN** `LuaSimulator.done_event` SHALL be set
- **AND** the message SHALL be recorded in `received_from_service`

#### Scenario: LuaSimulator poll loop runs concurrently

- **WHEN** the harness starts the event loop
- **THEN** `LuaSimulator` SHALL poll its SUB socket in a background `asyncio.Task`
- **AND** polling SHALL be non-blocking, not interfering with the service's own loop

### Requirement: E2eHarness fixture

The system SHALL provide an `E2eHarness` class wiring a real `ZMQRouter`, real `StateQueryClient`, real `DialogueGenerator`, and `LuaSimulator` together using a shared `zmq.asyncio.Context`.

The harness SHALL:
- Create one `zmq.asyncio.Context` shared by both `ZMQRouter` and `LuaSimulator`
- Start the `ZMQRouter` message loop as a background task
- Start the `LuaSimulator` poll loop as a background task
- Expose `run(scenario)` that: publishes the input, awaits `done_event` or timeout, returns `RunResult`
- Shut down cleanly — cancel background tasks, call `router.shutdown()`, terminate context

#### Scenario: Harness wires inproc transport

- **WHEN** `E2eHarness` initializes
- **THEN** `ZMQRouter` SHALL use `sub_endpoint="inproc://lua-to-python"` and `pub_endpoint="inproc://python-to-lua"`
- **AND** `LuaSimulator` SHALL bind on `inproc://lua-to-python` before `ZMQRouter` connects
- **AND** both SHALL share the same `zmq.asyncio.Context` instance

#### Scenario: Harness run returns RunResult

- **WHEN** `harness.run(scenario)` is called
- **THEN** the input ZMQ message SHALL be published
- **AND** the harness SHALL await `lua_sim.done_event` (default timeout: 5s)
- **AND** `RunResult` SHALL be returned containing `state_queries`, `http_calls`, `zmq_published`

#### Scenario: Harness timeout raises

- **WHEN** `dialogue.display` is not received within the timeout
- **THEN** `asyncio.TimeoutError` SHALL be raised
- **AND** all background tasks SHALL be cancelled before raising

### Requirement: JSON scenario files

The system SHALL support JSON scenario files under `tests/e2e/scenarios/`. Each file defines one complete test scenario.

Schema:
```json
{
  "description": "<human-readable name>",
  "input": {
    "topic": "<zmq topic, e.g. game.event>",
    "payload": { "<structured JSON object — harness serializes to wire format>" }
  },
  "state_mocks": {
    "<state.query.topic>": { "response": { ... } }
  },
  "llm_mocks": [
    { "response": "<string>" }
  ],
  "expected": {
    "state_queries": [
      { "topic": "<topic>", "payload": { "<request_id stripped>" } }
    ],
    "http_calls": [
      { "url": "<url>", "body": { "<full request body object>" } }
    ],
    "zmq_published": [
      { "topic": "<topic>", "payload": { "<structured JSON object>" } }
    ]
  }
}
```

`expected` keys are all optional — omitting a key means that boundary is not asserted.

#### Scenario: Scenario file is discovered and parametrized

- **WHEN** pytest collects `tests/e2e/test_scenarios.py`
- **THEN** one test SHALL be generated per `.json` file in `tests/e2e/scenarios/`
- **AND** the test name SHALL include the scenario filename

#### Scenario: Partial expected asserts only declared boundaries

- **WHEN** a scenario file contains `expected.zmq_published` but omits `expected.http_calls`
- **THEN** the harness SHALL assert `zmq_published` deeply
- **AND** SHALL NOT assert HTTP calls (no failure for missing `http_calls` key)

### Requirement: RunResult and deep equality assertions

The system SHALL provide a `RunResult` dataclass and `assert_scenario` function.

`RunResult` SHALL contain:
- `state_queries: list[dict]` — payloads of `state.query.*` messages sent by the service, with `request_id` stripped
- `http_calls: list[dict]` — each with `url: str`, `body: dict` (parsed from request content)
- `zmq_published: list[dict]` — each with `topic: str`, `payload: dict`, for all non-`state.query.*` publishes from the service

`assert_scenario(result, scenario)` SHALL perform deep `==` equality on each declared boundary.

#### Scenario: Deep equality on state queries

- **WHEN** `assert_scenario` is called with `expected.state_queries`
- **THEN** each actual state query payload SHALL have `request_id` stripped
- **AND** `actual_payload == expected_payload` SHALL be asserted (deep `==`, not pattern match)
- **AND** order SHALL be preserved

#### Scenario: Deep equality on HTTP request bodies

- **WHEN** `assert_scenario` is called with `expected.http_calls`
- **THEN** `actual.url == expected.url` SHALL be asserted
- **AND** `actual.body == expected.body` SHALL be asserted (full JSON object, deep `==`)

#### Scenario: Deep equality on ZMQ published payloads

- **WHEN** `assert_scenario` is called with `expected.zmq_published`
- **THEN** `actual.topic == expected.topic` SHALL be asserted
- **AND** `actual.payload == expected.payload` SHALL be asserted (deep `==`)

### Requirement: Payload capture to artifacts

The system SHALL write captured payloads to `.test_artifacts/last_run/payloads.json` after each test, keyed by test node ID.

#### Scenario: Payloads written after test

- **WHEN** a test in `test_scenarios.py` completes (pass or fail)
- **THEN** a JSON file SHALL be written containing `state_queries`, `http_calls`, and `zmq_published` for that test
- **AND** the MCP server SHALL be able to read this file via `get_captured_payloads`
