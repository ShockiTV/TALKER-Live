## MODIFIED Requirements

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
    { "response": "<string>", "request": { "<required: expected HTTP request body>" } }
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

The `llm_mocks[].request` field is **required**. `assert_scenario` SHALL verify the actual HTTP request body matches the declared `request` object using deep equality. Omitting `request` is a test error and SHALL cause the test to fail with a descriptive message.

All scenario payloads SHALL be validated against `docs/zmq-api.yaml` during pytest collection. Specifically:
- `input.payload` SHALL validate against the payload schema for `input.topic`
- Each `state_mocks.<topic>.response` SHALL validate against the response schema for that topic
- Each `expected.zmq_published[].payload` SHALL validate against the payload schema for that entry's topic
- Each `expected.state_queries[].payload` SHALL validate against the request schema for that entry's topic

#### Scenario: Scenario file is discovered and parametrized

- **WHEN** pytest collects `tests/e2e/test_scenarios.py`
- **THEN** one test SHALL be generated per `.json` file in `tests/e2e/scenarios/`
- **AND** the test name SHALL include the scenario filename

#### Scenario: Partial expected asserts only declared boundaries

- **WHEN** a scenario file contains `expected.zmq_published` but omits `expected.http_calls`
- **THEN** the harness SHALL assert `zmq_published` deeply
- **AND** SHALL NOT assert HTTP calls (no failure for missing `http_calls` key)

#### Scenario: Scenario payloads validated against ZMQ API schema

- **WHEN** pytest collects a scenario file
- **THEN** all payloads in `input`, `state_mocks`, and `expected` SHALL be validated against the compiled `docs/zmq-api.yaml` schema
- **AND** validation failures SHALL be reported as collection errors with descriptive messages

#### Scenario: llm_mocks request body assertion

- **WHEN** a scenario file is executed
- **THEN** `assert_scenario` SHALL verify `len(http_calls) == len(llm_mocks)`
- **AND** for each index `i`, `http_calls[i].body` SHALL equal `llm_mocks[i].request` using deep equality
- **AND** mismatches SHALL produce a clear error showing expected vs actual request body

#### Scenario: llm_mocks missing request field is an error

- **WHEN** a scenario file contains `llm_mocks[i]` without a `request` field
- **THEN** the test SHALL fail with: `"llm_mocks[i] is missing a 'request' field — all scenario llm_mocks entries must declare expected request bodies."`
- **AND** the test author SHALL add the expected request body to fix the failure
