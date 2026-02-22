# integration-event-coverage

## Purpose

Per-EventType integration test files for the Python service lifecycle. One `test_<type>_lifecycle.py` file per EventType in `tests/integration/`, each containing a happy-path test with full JSON visibility and edge case tests using the light assertion pattern.

## Requirements

### Requirement: Per-EventType integration test files

The system SHALL have one integration test file per EventType in `tests/integration/`, named `test_<type>_lifecycle.py` (lowercase). Each file SHALL contain:

1. One happy-path test with full 14-step JSON visibility (matching the `test_map_transition_lifecycle.py` pattern)
2. Edge case tests using the light pattern: `describe_event()` assertion + `content_patterns` matching on LLM requests

The following files SHALL exist (14 EventTypes — ACTION is not a real EventType; `action` is a context field on ARTIFACT/TASK events):
- `test_death_lifecycle.py` (migrated from `test_event_lifecycle.py` T1 + new edge cases)
- `test_dialogue_lifecycle.py`
- `test_callout_lifecycle.py`
- `test_taunt_lifecycle.py`
- `test_artifact_lifecycle.py`
- `test_anomaly_lifecycle.py`
- `test_map_transition_lifecycle.py` (existing — already has 9+ tests)
- `test_emission_lifecycle.py`
- `test_injury_lifecycle.py`
- `test_sleep_lifecycle.py`
- `test_task_lifecycle.py`
- `test_weapon_jam_lifecycle.py`
- `test_reload_lifecycle.py`
- `test_idle_lifecycle.py`

#### Scenario: Each EventType has a dedicated integration file

- **WHEN** tests are discovered in `tests/integration/`
- **THEN** each of the 14 EventTypes SHALL have a corresponding `test_<type>_lifecycle.py` file
- **AND** each file SHALL contain at least one test function

#### Scenario: Happy path uses full 14-step JSON visibility

- **WHEN** the happy-path test in a per-type file executes
- **THEN** it SHALL define inline JSON constants for all 14 lifecycle steps (INPUT_EVENT through PUBLISH_REQUEST)
- **AND** it SHALL call `run_lifecycle()` and assert state requests, LLM requests, and published output

### Requirement: Light pattern for edge case tests

Edge case tests SHALL use a minimal assertion pattern:

1. Define only `INPUT_EVENT` and `EXPECTED_DESCRIPTION` as inline constants
2. Call `describe_event()` on the input and assert it matches `EXPECTED_DESCRIPTION`
3. Optionally run the full lifecycle and assert `content_patterns` appear in LLM request messages

#### Scenario: Edge case tests assert describe_event output

- **WHEN** an edge case test executes
- **THEN** it SHALL create an `Event` from the `INPUT_EVENT` context
- **AND** SHALL assert `describe_event(event) == EXPECTED_DESCRIPTION`

#### Scenario: Edge case tests assert content_patterns in LLM requests

- **WHEN** an edge case test runs the full lifecycle
- **THEN** it SHALL verify that each expected pattern from `content_patterns` appears in the corresponding LLM request message content (case-insensitive regex search)

### Requirement: EventType-specific edge cases

Each EventType's integration file SHALL cover the following edge cases where applicable:

| EventType | Edge Cases |
|-----------|-----------|
| DEATH | Victim only (no killer), unknown faction victim |
| DIALOGUE | Empty text, long text |
| CALLOUT | Missing target, mutant target |
| TAUNT | Missing taunter |
| ARTIFACT | Different actions (found, detected, picked_up) |
| ANOMALY | Various anomaly types |
| MAP_TRANSITION | (already covered — 8 edge cases in existing file) |
| EMISSION | Static event (no variations needed beyond happy path) |
| INJURY | Severe vs normal severity |
| SLEEP | Zero hours, large hours |
| TASK | Different task_status values (completed, failed, updated), with/without task_giver |
| WEAPON_JAM | (minimal — actor only) |
| RELOAD | (minimal — actor only) |
| IDLE | (minimal — actor only) |

#### Scenario: Edge cases cover context field variations

- **WHEN** integration tests for EventType X execute
- **THEN** they SHALL cover the documented edge cases for that type
- **AND** each edge case SHALL verify `describe_event()` produces the correct output for that variation

### Requirement: Retire orphaned L9 matrix

The `TestEventLifecycleL9` class in `test_event_lifecycle.py` SHALL be removed. Its single implemented test (T1: DEATH full lifecycle) SHALL be migrated to `test_death_lifecycle.py`.

#### Scenario: L9 class removed from test_event_lifecycle.py

- **WHEN** the migration is complete
- **THEN** `test_event_lifecycle.py` SHALL either be deleted entirely or contain only shared documentation
- **AND** `test_death_lifecycle.py` SHALL contain the T1 test with full 14-step JSON visibility

#### Scenario: No test regression from L9 removal

- **WHEN** all integration tests are run
- **THEN** the test count SHALL be equal to or greater than before the migration
- **AND** all previously passing tests SHALL continue to pass
