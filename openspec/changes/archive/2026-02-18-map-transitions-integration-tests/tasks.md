## 1. Test File Setup

- [x] 1.1 Create `talker_service/tests/integration/test_map_transition_lifecycle.py` with module docstring and imports
- [x] 1.2 Copy mock infrastructure from `test_event_lifecycle.py` (MockStateClient, MockLLMClient, run_lifecycle helper)

## 2. Happy Path Test

- [x] 2.1 Define all 14 JSON constants for happy path (player with companion, first visit to Garbage from Cordon)
- [x] 2.2 Implement `test_happy_path_with_companions` test method with full lifecycle assertions

## 3. Visit Count Edge Cases (INPUT_EVENT + EXPECTED_DESCRIPTION pattern)

- [x] 3.1 Implement `test_visit_count_first_time` with JSON constants (visit_count=1 → "for the first time")
- [x] 3.2 Implement `test_visit_count_second_time` with JSON constants (visit_count=2 → "for the 2nd time")
- [x] 3.3 Implement `test_visit_count_third_time` with JSON constants (visit_count=3 → "for the 3rd time")
- [x] 3.4 Implement `test_visit_count_many_times` with JSON constants (visit_count=5 → "again")

## 4. Companion Edge Cases (INPUT_EVENT + EXPECTED_DESCRIPTION pattern)

- [x] 4.1 Implement `test_no_companions` with JSON constants (empty list → no "travelling companions" text)
- [x] 4.2 Implement `test_multiple_companions` with JSON constants (two companions → "Hip and Fanatic")

## 5. Location Resolution Edge Cases (INPUT_EVENT + EXPECTED_DESCRIPTION pattern)

- [x] 5.1 Implement `test_unknown_destination` with JSON constants (unknown ID → technical ID fallback)
- [x] 5.2 Implement `test_empty_source` with JSON constants (empty string → "somewhere" fallback)

## 6. Verification

- [x] 6.1 Run test suite and verify all tests pass

## 7. Fixture Refinements (Post-Implementation)

- [x] 7.1 Update SCENE_CONTEXT_RESPONSE POI field to use human-readable names (`Truck depot`, `Rookie Village`) instead of technical IDs
- [x] 7.2 Add personality field to witnesses in `test_event_lifecycle.py` (Wolf: `gruff_but_fair`, Petruha: `generic.15`)
- [x] 7.3 Update LLM_SPEAKER_REQUEST CANDIDATES format to include personality description
- [x] 7.4 Correct step ordering in `test_event_lifecycle.py` docstring to match actual execution flow (speaker selection before state queries)
- [x] 7.5 Update REPUTATION section to use numeric scale format matching actual builder output
