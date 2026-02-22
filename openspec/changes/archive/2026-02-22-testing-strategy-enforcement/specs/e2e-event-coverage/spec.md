## ADDED Requirements

### Requirement: Per-EventType E2E scenario files

The system SHALL have one E2E scenario JSON file per EventType in `tests/e2e/scenarios/`. Each file SHALL define a happy-path lifecycle for that event type, including input event, state mocks, LLM mocks with request bodies, and expected outputs.

The following EventType scenario files SHALL exist:
- `death_wolf_full.json` (existing, retrofitted with request bodies)
- `dialogue_npc_speaks.json`
- `callout_spotted_enemy.json`
- `taunt_enemy_taunts.json`
- `artifact_found.json`
- `anomaly_encountered.json`
- `map_transition_to_garbage.json`
- `emission_sweep.json`
- `injury_severe.json`
- `sleep_rest.json`
- `task_completed.json` (existing — `task_with_giver.json` or `task_with_disguised_actor.json` covers this)
- `weapon_jam.json`
- `reload_weapon.json`
- `idle_nearby.json`
- `action_custom.json`

Each scenario file SHALL include `llm_mocks[].request` fields containing the complete expected HTTP request body (messages array, model, temperature, max_tokens) for all LLM calls.

#### Scenario: All 15 EventTypes have at least one E2E scenario

- **WHEN** pytest collects `tests/e2e/test_scenarios.py`
- **THEN** at least 15 parametrized test cases SHALL be generated (one per EventType)
- **AND** each scenario SHALL exercise the full lifecycle: input → speaker selection → state queries → dialogue generation → `dialogue.display` output

#### Scenario: New scenario JSON includes request body verification

- **WHEN** a new EventType scenario file is loaded
- **THEN** each `llm_mocks[]` entry SHALL include a `request` object
- **AND** `request` SHALL contain `messages` (array of `{role, content}`) and model parameters
- **AND** `assertions.py._assert_llm_mock_requests()` SHALL verify the actual HTTP body matches

#### Scenario: Existing death_wolf_full.json retrofitted with request bodies

- **WHEN** `death_wolf_full.json` is loaded
- **THEN** each `llm_mocks[]` entry SHALL include a `request` field
- **AND** the assertions SHALL verify the LLM request body matches the expected prompt content

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
| ACTION | `actor` (Character), `action` (string) |

#### Scenario: Scenario input matches EventType schema

- **WHEN** a scenario file for EventType X is loaded
- **THEN** `input.payload.event.type` SHALL match X (case-insensitive)
- **AND** `input.payload.event.context` SHALL contain all required fields for that EventType
