## Context

The Python test suite has 452 passing tests across three layers: unit (~430), integration (10), and e2e (12). However, lifecycle coverage — where a `game.event` input flows through speaker selection, state queries, LLM calls, and `dialogue.display` output — exists for only 3 of 15 EventTypes:

| EventType | E2E | Integration | Unit |
|-----------|-----|-------------|------|
| DEATH | 1 scenario | 1 test (L9 T1) | ✅ describe_event |
| TASK | 2 scenarios | — | ✅ describe_event |
| MAP_TRANSITION | — | 9 tests | ✅ describe_event |
| 12 others | — | — | ✅ describe_event only |

Current problems:
1. `test_event_lifecycle.py` defines an L9 orthogonal array covering 9 test combinations (DEATH×3, DIALOGUE×3, ARTIFACT×3), but only T1 is implemented. The remaining 8 slots are dead code.
2. Integration mock infrastructure (`MockStateClient`, `MockPublisher`, `MockLLMClient`, `LifecycleSnapshot`, `run_lifecycle`) is duplicated verbatim between `test_event_lifecycle.py` and `test_map_transition_lifecycle.py`.
3. E2E scenario `death_wolf_full.json` already captures HTTP calls via respx but does not declare expected `llm_mocks[].request` bodies — even though `assertions.py` already supports this field.

## Goals / Non-Goals

**Goals:**
- 1 E2E happy-path scenario JSON per EventType (15 total) with full LLM request body verification
- Per-EventType integration test files with edge case coverage using the light pattern (`describe_event` assertions + `content_patterns` matching)
- Shared mock module eliminating duplication across integration files
- Retire the orphaned L9 matrix, migrating T1 to `test_death_lifecycle.py`

**Non-Goals:**
- Changing production code (prompts, dialogue generator, LLM clients)
- Adding new unit tests for `describe_event` (already well-covered in `test_prompts.py`)
- Cross-EventType combination testing (the old L9 approach — replaced by per-type files)
- Coverage for `COMPRESSED` pseudo-events (internal to memory system, not a `game.event` input)

## Decisions

### D1: Per-EventType integration files instead of orthogonal array

**Decision**: One integration test file per EventType (`test_<type>_lifecycle.py`) instead of a multi-type matrix.

**Rationale**: The L9 orthogonal array tested combinations of (EventType × scene_context × world_state × memory), but only 1 of 9 was implemented after months. Per-type files are:
- Easier to assign and complete independently
- Better aligned with how `describe_event` branches by type
- More maintainable: edge cases are co-located with their EventType

**Alternative rejected**: Keeping L9 but completing missing tests. This loses the per-type focus and mixes concerns across event types.

### D2: Light pattern for integration edge cases

**Decision**: Edge case tests verify `describe_event()` output and `content_patterns` on LLM request messages. No full 14-step JSON inline.

**Rationale**: The happy path (with full 14-step verification) lives in the E2E layer via scenario JSON. Integration edge cases focus on:
- `describe_event()` correctly formatting each context variation
- LLM prompts containing expected patterns (via regex `content_patterns`)
- Published output having correct structure

This matches the existing `test_map_transition_lifecycle.py` pattern which has 1 happy path + 8 light edge case tests.

**Alternative rejected**: Full 14-step JSON in every integration test. Too verbose for edge cases, leads to copy-paste fragility.

### D3: Shared mock module in `conftest.py`

**Decision**: Extract `MockStateClient`, `MockPublisher`, `MockLLMClient`, `LifecycleSnapshot`, and `run_lifecycle` into `tests/integration/conftest.py`.

**Rationale**: These classes are identical between `test_event_lifecycle.py` and `test_map_transition_lifecycle.py`. pytest's conftest.py is the idiomatic location for shared test fixtures — any test file in the integration directory can import them directly.

**Alternative rejected**: Separate `helpers.py` module. Works but adds an import that conftest avoids.

### D4: Add `llm_mocks[].request` to existing death_wolf_full.json

**Decision**: Retrofit the existing `death_wolf_full.json` with `request` fields in `llm_mocks[]` entries. All new scenario JSONs include request bodies from the start.

**Rationale**: The assertion code in `assertions.py._assert_llm_mock_requests()` already supports this — it just skips mocks without a `request` key. Adding the field is non-breaking and provides full round-trip verification.

### D5: E2E scenario JSON per EventType with full request body

**Decision**: Each scenario JSON includes complete `llm_mocks[].request` objects specifying the exact HTTP request body sent to the LLM API (messages array + model/temperature/max_tokens).

**Rationale**: E2E tests should verify the full wire contract. The harness captures HTTP calls via respx; asserting request bodies catches prompt regressions, incorrect model parameters, and message ordering bugs.

### D6: Grouping of low-context EventTypes

**Decision**: WEAPON_JAM, RELOAD, IDLE, and ACTION share a similar actor-only context pattern. Each still gets its own scenario and integration file, but scenarios can be minimal (fewer state mocks needed since these are "junk events" that may skip dialogue in some configurations).

**Rationale**: These events have simpler `describe_event` output and fewer context fields, so their test data is naturally shorter. Keeping them separate per-type maintains the 1:1 EventType-to-file mapping.

## Risks / Trade-offs

- **Volume of test files**: 12 new integration files + 12 new scenario JSONs is significant. → Mitigated by following established patterns and keeping edge case tests concise.
- **Scenario JSON maintenance**: Full request bodies in scenario JSON are brittle to prompt changes. → Mitigated by running e2e tests in CI; failures are caught immediately and the JSON is the single source of truth for expected prompts.
- **Junk event filtering**: Some EventTypes (WEAPON_JAM, RELOAD, ARTIFACT, ANOMALY) are flagged as "junk" and may be filtered before dialogue generation. Integration tests must account for the filtering path. → Tests should verify both the filtered and unfiltered paths where applicable.
- **Shared conftest migration**: Moving mocks to conftest may briefly break imports if done in wrong order. → Mitigated by doing extraction as the first task before adding new files.
