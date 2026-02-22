# e2e-event-coverage

## Purpose

Per-EventType E2E scenario JSON files in `tests/e2e/scenarios/`. Each file defines one complete happy-path lifecycle test with full LLM request body verification via `llm_mocks[].request`.

## Requirements

### Requirement: Per-EventType E2E scenario files

The system SHALL have one E2E scenario JSON file per EventType in `tests/e2e/scenarios/`. Each file SHALL define a happy-path lifecycle for that event type, including input event, state mocks, LLM mocks with request bodies, and expected outputs.

The following EventType scenario files SHALL exist (14 EventTypes — ACTION is not a real EventType; `action` is a context field on ARTIFACT/TASK events):
- `death_wolf_full.json` (retrofitted with request bodies)
- `dialogue_npc_speaks.json`
- `callout_spotted_enemy.json`
- `taunt_enemy_taunts.json`
- `artifact_found.json`
- `anomaly_encountered.json`
- `map_transition_to_garbage.json`
- `emission_sweep.json`
- `injury_severe.json`
- `sleep_rest.json`
- `task_with_giver.json` or `task_with_disguised_actor.json` (covers TASK)
- `weapon_jam.json`
- `reload_weapon.json`
- `idle_nearby.json`

Each scenario file SHALL include `llm_mocks[].request` fields containing the complete expected HTTP request body (messages array, model, temperature, max_tokens) for all LLM calls.

#### Scenario: All 14 EventTypes have at least one E2E scenario

- **WHEN** pytest collects `tests/e2e/test_scenarios.py`
- **THEN** at least 14 parametrized test cases SHALL be generated (one per EventType)
- **AND** each scenario SHALL exercise the full lifecycle: input → speaker selection → state queries → dialogue generation → `dialogue.display` output

#### Scenario: Scenario JSON includes request body verification

- **WHEN** an EventType scenario file is loaded
- **THEN** each `llm_mocks[]` entry SHALL include a `request` object
- **AND** `request` SHALL contain `messages` (array of `{role, content}`) and model parameters
- **AND** `assertions.py._assert_llm_mock_requests()` SHALL verify the actual HTTP body matches

### Requirement: Scenario context fields match EventType

Each scenario's `input.payload.event.context` SHALL contain the fields required by that EventType's `describe_event()` implementation.

| EventType | Required Context Fields |
|-----------|------------------------|
| DEATH | `killer`, `victim` (Character objects) |
| DIALOGUE | `speaker` (Character), `text` (string) |
| CALLOUT | `spotter`, `target` (Character objects) |
| TAUNT | `taunter` (Character object) |
| ARTIFACT | `actor` (Character), `action` (string), `item_name` (string) |
| ANOMALY | `actor` (Character), `anomaly_type` (string) |
| MAP_TRANSITION | `actor` (Character), `source`, `destination` (string), `visit_count` (int), `companions` (array) |
| EMISSION | (no required fields — static description) |
| INJURY | `actor` (Character), `severity` (string) |
| SLEEP | `actor` (Character), `hours` (int) |
| TASK | `actor` (Character), `task_status`, `task_name` (strings), `task_giver` (Character, optional) |
| WEAPON_JAM | `actor` (Character) |
| RELOAD | `actor` (Character) |
| IDLE | `actor` (Character) |

#### Scenario: Scenario input matches EventType schema

- **WHEN** a scenario file for EventType X is loaded
- **THEN** `input.payload.event.type` SHALL match X (case-insensitive)
- **AND** `input.payload.event.context` SHALL contain all required fields for that EventType
