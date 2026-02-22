## ADDED Requirements

### Requirement: Shared mock classes in integration conftest

The system SHALL provide shared mock classes in `tests/integration/conftest.py` (or a helper imported by conftest) that eliminate duplication across per-EventType integration test files.

The following classes SHALL be extracted:
- `MockStateClient` — records batch query requests, returns configured responses by resource type
- `MockPublisher` — records published `{topic, payload}` dicts
- `MockLLMClient` — records LLM requests as `{messages, options}` dicts, returns pre-configured response strings in order
- `LifecycleSnapshot` — dataclass containing `input_event`, `state_requests`, `llm_requests`, `published`

The following function SHALL be provided:
- `run_lifecycle(input_event_json, scene_json, characters_alive_json, memory_json, character_json, llm_responses) -> LifecycleSnapshot` — wires mocks to `DialogueGenerator` and executes a single event lifecycle

#### Scenario: MockStateClient routes batch queries

- **WHEN** `execute_batch` is called with a batch containing `store.memories`, `query.character`, `query.world`, and `query.characters_alive` sub-queries
- **THEN** each sub-query SHALL be routed to the corresponding configured response
- **AND** each request SHALL be recorded as `{"method": "<method_name>", "args": {<params>}}`

#### Scenario: MockLLMClient returns responses in order

- **WHEN** `complete()` is called N times
- **THEN** the Nth call SHALL return `response_jsons[N-1]`
- **AND** if N exceeds the response list length, SHALL return `"Fallback response."`
- **AND** each call SHALL record `{"messages": [...], "options": {temperature, max_tokens}}`

#### Scenario: run_lifecycle returns LifecycleSnapshot

- **WHEN** `run_lifecycle(...)` is called
- **THEN** it SHALL construct mocks from the provided JSON strings
- **AND** SHALL create a `DialogueGenerator` with those mocks
- **AND** SHALL call `generate_from_event` on the input event
- **AND** SHALL return a `LifecycleSnapshot` with all recorded requests and published messages

### Requirement: Shared assertion helpers

The conftest SHALL also provide assertion helpers used by per-EventType files:

- `assert_state_requests(actual, expected_json)` — asserts method names and args match
- `assert_llm_requests(actual, expected_json)` — asserts content_patterns appear in LLM messages (regex, case-insensitive)
- `assert_published(actual, expected_json)` — asserts topic and payload keys match

#### Scenario: assert_llm_requests checks content_patterns

- **WHEN** `assert_llm_requests` is called with expected JSON containing `content_patterns` arrays
- **THEN** for each expected message, all patterns SHALL be searched in the concatenated content of matching role messages
- **AND** search SHALL be case-insensitive using `re.search`
- **AND** missing patterns SHALL produce a clear assertion error with the pattern and role
