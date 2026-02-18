## ADDED Requirements

### Requirement: Happy path test with full JSON visibility
The test suite SHALL include one complete lifecycle test for MAP_TRANSITION events that displays all 14 JSON constants in chronological order (input event, state queries, LLM requests/responses, published output).

#### Scenario: Player with companion travels to known location for first time
- **WHEN** a MAP_TRANSITION event is received with source="l01_escape", destination="l02_garbage", visit_count=1, and one companion
- **THEN** the test verifies the full 14-step lifecycle executes correctly
- **AND** all JSON constants are visible inline in the test for debugging

### Requirement: Edge case tests with JSON constant pattern
Each edge case test SHALL define two JSON constants inline:
1. `INPUT_EVENT` - The MAP_TRANSITION event context being tested
2. `EXPECTED_DESCRIPTION` - The complete expected describe_event() output string

This provides full visibility into the test data without requiring the full 14-step lifecycle constants.

#### Scenario: Visit count first time
- **WHEN** INPUT_EVENT has visit_count=1
- **THEN** EXPECTED_DESCRIPTION contains "for the first time"

#### Scenario: Visit count second time
- **WHEN** INPUT_EVENT has visit_count=2
- **THEN** EXPECTED_DESCRIPTION contains "for the 2nd time"

#### Scenario: Visit count third time
- **WHEN** INPUT_EVENT has visit_count=3
- **THEN** EXPECTED_DESCRIPTION contains "for the 3rd time"

#### Scenario: Visit count many times
- **WHEN** INPUT_EVENT has visit_count >= 4
- **THEN** EXPECTED_DESCRIPTION contains "again"

#### Scenario: No companions
- **WHEN** INPUT_EVENT has empty companions list
- **THEN** EXPECTED_DESCRIPTION does NOT contain "travelling companions"

#### Scenario: Multiple companions
- **WHEN** INPUT_EVENT has companions ["Hip", "Fanatic"]
- **THEN** EXPECTED_DESCRIPTION contains "Hip and Fanatic"

#### Scenario: Unknown destination
- **WHEN** INPUT_EVENT has destination="unknown_zone_id"
- **THEN** EXPECTED_DESCRIPTION uses "unknown_zone_id" as fallback location name
- **AND** EXPECTED_DESCRIPTION does NOT include a location description suffix

#### Scenario: Empty source
- **WHEN** INPUT_EVENT has source=""
- **THEN** EXPECTED_DESCRIPTION uses "somewhere" as source location
