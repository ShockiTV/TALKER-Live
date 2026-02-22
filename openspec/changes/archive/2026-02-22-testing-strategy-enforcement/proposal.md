## Why

The Python test suite has 452 passing tests but covers only 3 of 15 EventTypes at the lifecycle (integration/e2e) level. DEATH, TASK, and MAP_TRANSITION have coverage; the remaining 12 (DIALOGUE, CALLOUT, TAUNT, ARTIFACT, ANOMALY, EMISSION, INJURY, SLEEP, WEAPON_JAM, RELOAD, IDLE, ACTION) have zero lifecycle coverage. The existing `test_event_lifecycle.py` contains an orphaned L9 orthogonal array matrix with only 1 of 9 tests implemented — a leftover from before the E2E harness existed. The integration and e2e layers need systematic per-EventType coverage with a clean, maintainable pattern.

## What Changes

- Add 12 new E2E scenario JSON files (one happy-path per uncovered EventType) with full request body verification in `llm_mocks[].request`
- Add `llm_mocks[].request` verification to the existing `death_wolf_full.json` scenario
- Create per-EventType integration test files following the light pattern (`describe_event` + `content_patterns`) from `test_map_transition_lifecycle.py`
- Extract shared mock infrastructure (`MockStateClient`, `MockPublisher`, `MockLLMClient`, `LifecycleSnapshot`, `run_lifecycle`) from duplicated code in integration test files into a shared conftest or helper module
- Retire the orphaned L9 matrix from `test_event_lifecycle.py`, replacing it with per-type files
- Update the E2E harness assertions to support `llm_mocks[].request` verification in scenario JSON

## Capabilities

### New Capabilities
- `e2e-event-coverage`: Per-EventType E2E scenario JSON files with full request body verification
- `integration-event-coverage`: Per-EventType integration test files with describe_event + content_patterns edge case assertions
- `shared-integration-mocks`: Extracted shared mock infrastructure for integration lifecycle tests

### Modified Capabilities
- `e2e-test-harness`: Add `llm_mocks[].request` assertion support for verifying exact LLM request bodies in scenario JSON

## Impact

- **Test files**: 12 new E2E scenario JSONs in `talker_service/tests/e2e/scenarios/`, ~12 new integration test files in `talker_service/tests/integration/`, 1 new shared mock module
- **E2E harness**: `assertions.py` and/or `harness.py` modified to support request body verification
- **Removed**: `test_event_lifecycle.py` L9 matrix class (replaced by per-type files; T1 DEATH test migrated to `test_death_lifecycle.py`)
- **No production code changes** — this is purely test infrastructure
