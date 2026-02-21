# e2e-test-harness (delta)

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
