## Why

The existing integration test file (`test_event_lifecycle.py`) uses an L9 orthogonal array covering only DEATH, DIALOGUE, and ARTIFACT event types. MAP_TRANSITION events have unique context fields (source, destination, visit_count, companions) that aren't exercised by current tests, risking regressions in location name resolution, visit count formatting, and companion list handling.

## What Changes

- Add a new integration test file specifically for MAP_TRANSITION event lifecycle
- Implement one full "happy path" test with complete 14-step JSON visibility (matching existing T1 format)
- Implement edge case tests with partial JSON focusing on the "hot area" (describe_event() output variations)

## Capabilities

### New Capabilities
- `map-transition-integration-tests`: Integration tests covering MAP_TRANSITION event handling through the full dialogue generation pipeline, including variations for visit count, companions, and location resolution

### Modified Capabilities
<!-- None - this is additive test coverage -->

## Impact

- New test file: `talker_service/tests/integration/test_map_transition_lifecycle.py`
- No changes to production code
- Depends on existing test infrastructure from `test_event_lifecycle.py`
