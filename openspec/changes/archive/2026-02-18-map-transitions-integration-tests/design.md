## Context

The existing `test_event_lifecycle.py` provides a template for full-visibility integration tests using 14-step JSON constants that trace the complete dialogue generation pipeline. Currently only T1 (DEATH event) is implemented.

MAP_TRANSITION events have unique context fields not shared with other event types:
- `source` / `destination` - Technical location IDs requiring resolution
- `visit_count` - Affects descriptive text ("for the first time", "for the 2nd time", etc.)
- `companions` - List of companion characters affecting travel description

The prompt building logic for MAP_TRANSITION is in `prompts/helpers.py:describe_event()` (lines 226-265).

## Goals / Non-Goals

**Goals:**
- Full integration test coverage for MAP_TRANSITION event lifecycle
- One happy-path test with complete 14-step JSON visibility
- Edge case tests covering context variations (visit count, companions, location resolution)
- Establish pattern for adding other event type test files

**Non-Goals:**
- Modifying the existing L9 orthogonal array in `test_event_lifecycle.py`
- Testing all 13 event types in this change
- Live LLM testing (continues using mock LLM clients)

## Decisions

### Decision 1: Separate file per event type
**Choice**: Create `test_map_transition_lifecycle.py` rather than extend existing file

**Rationale**: 
- Keeps test files focused and maintainable
- Avoids bloating `test_event_lifecycle.py` 
- Establishes scalable pattern for other event types
- L9 matrix stays in original file as regression suite

**Alternatives considered**:
- Extend L9 to L27/L36 covering more event types → Combinatorial explosion, test file becomes unwieldy
- Add tests inline to existing file → File grows too large, mixed concerns

### Decision 2: JSON constant pattern for all tests
**Choice**: Happy path shows all 14 JSON constants; edge cases show INPUT_EVENT + EXPECTED_DESCRIPTION constants

**Rationale**:
- Full JSON verbosity aids debugging and documentation
- Edge cases still have visible test data, just focused on the "hot area"
- Consistent pattern across all tests (JSON constants, not magic strings)

### Decision 3: Edge cases use two-constant pattern
**Choice**: Edge cases define INPUT_EVENT (event context) and EXPECTED_DESCRIPTION (full describe_event() output string)

**Rationale**:
- The unique behavior of MAP_TRANSITION is in describe_event()
- Full expected output string provides clear visibility into what the test expects
- JSON constants pattern matches happy path style, just with fewer constants

## Risks / Trade-offs

**[Risk]** Test maintenance burden if describe_event() format changes
→ EXPECTED_DESCRIPTION constants make it clear what output is expected; easy to update

**[Risk]** Edge cases don't verify full lifecycle
→ Happy path test covers full lifecycle; edge cases focus on unique describe_event() behavior

**[Trade-off]** Less coverage than full L9 for this event type
→ Acceptable: orthogonal variation (Scene/World/Memory) is well-tested by existing L9
