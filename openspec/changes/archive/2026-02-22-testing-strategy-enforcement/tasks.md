## 1. Shared Mock Infrastructure

- [x] 1.1 Extract `MockStateClient`, `MockPublisher`, `MockLLMClient`, `LifecycleSnapshot`, `run_lifecycle` into `tests/integration/conftest.py`
- [x] 1.2 Extract `assert_state_requests`, `assert_llm_requests`, `assert_published` into `tests/integration/conftest.py`
- [x] 1.3 Update `test_map_transition_lifecycle.py` to import from conftest instead of defining its own mocks
- [x] 1.4 Verify all existing integration tests still pass after extraction

## 2. Integration: Per-EventType Lifecycle Files

- [x] 2.1 Create `test_death_lifecycle.py` — migrate T1 from `test_event_lifecycle.py` + add edge cases (no killer, unknown faction)
- [x] 2.2 Create `test_dialogue_lifecycle.py` — happy path + edge cases (empty text, long text)
- [x] 2.3 Create `test_callout_lifecycle.py` — happy path + edge cases (missing target, mutant target)
- [x] 2.4 Create `test_taunt_lifecycle.py` — happy path + edge case (missing taunter)
- [x] 2.5 Create `test_artifact_lifecycle.py` — happy path + edge cases (found, detected, picked_up actions)
- [x] 2.6 Create `test_anomaly_lifecycle.py` — happy path + edge cases (various anomaly types)
- [x] 2.7 Create `test_emission_lifecycle.py` — happy path (static event, minimal edge cases)
- [x] 2.8 Create `test_injury_lifecycle.py` — happy path + edge cases (severe vs normal)
- [x] 2.9 Create `test_sleep_lifecycle.py` — happy path + edge cases (zero hours, large hours)
- [x] 2.10 Create `test_task_lifecycle.py` — happy path + edge cases (completed/failed/updated status, with/without task_giver)
- [x] 2.11 Create `test_weapon_jam_lifecycle.py` — happy path
- [x] 2.12 Create `test_reload_lifecycle.py` — happy path
- [x] 2.13 Create `test_idle_lifecycle.py` — happy path
- [x] ~~2.14 Create `test_action_lifecycle.py`~~ — **reverted**: ACTION is not a real EventType (only 14 exist); `action` is a context field on ARTIFACT/TASK events. File created then deleted.

## 3. Retire Orphaned L9 Matrix

- [x] 3.1 Delete `TestEventLifecycleL9` class from `test_event_lifecycle.py`
- [x] 3.2 Delete `test_event_lifecycle.py` if no other content remains (or keep as doc-only)
- [x] 3.3 Verify no test regression — total integration test count >= previous count

## 4. E2E: Retrofit Existing Scenarios

- [x] 4.1 Add `llm_mocks[].request` fields to `death_wolf_full.json`
- [x] 4.2 Add `llm_mocks[].request` fields to `task_with_giver.json`
- [x] 4.3 Add `llm_mocks[].request` fields to `task_with_disguised_actor.json`
- [x] 4.4 Verify retrofitted scenarios still pass

## 5. E2E: New EventType Scenarios

- [x] 5.1 Create `dialogue_npc_speaks.json` with full request body
- [x] 5.2 Create `callout_spotted_enemy.json` with full request body
- [x] 5.3 Create `taunt_enemy_taunts.json` with full request body
- [x] 5.4 Create `artifact_found.json` with full request body
- [x] 5.5 Create `anomaly_encountered.json` with full request body
- [x] 5.6 Create `map_transition_to_garbage.json` with full request body
- [x] 5.7 Create `emission_sweep.json` with full request body
- [x] 5.8 Create `injury_severe.json` with full request body
- [x] 5.9 Create `sleep_rest.json` with full request body
- [x] 5.10 Create `weapon_jam.json` with full request body
- [x] 5.11 Create `reload_weapon.json` with full request body
- [x] 5.12 Create `idle_nearby.json` with full request body
- [x] ~~5.13 Create `action_custom.json`~~ — **reverted**: same as 2.14; file created then deleted.

## 6. Final Validation

- [x] 6.1 Run full test suite — all existing + new tests pass
- [x] 6.2 Verify all 14 EventTypes have at least one E2E scenario and one integration file
