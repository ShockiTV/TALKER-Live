# lua-event-creation (delta)

## ADDED Requirements

### Requirement: MAP_TRANSITION Event Context Structure

MAP_TRANSITION events SHALL include technical location IDs and travel metadata.

Context fields:
- `actor`: Character who traveled (player)
- `source`: Technical location ID of origin (e.g., `l01_escape`)
- `destination`: Technical location ID of arrival (e.g., `l02_garbage`)
- `visit_count`: Integer count of times player has visited destination
- `companions`: Array of Character objects who traveled with the player

The event SHALL NOT include `destination_description` - descriptions are resolved by Python.

#### Scenario: Map transition with companions
- **WHEN** player travels from Cordon to Garbage with companion Hip
- **THEN** event.context.source equals "l01_escape"
- **AND** event.context.destination equals "l02_garbage"
- **AND** event.context.visit_count equals number of previous visits + 1
- **AND** event.context.companions contains Hip's Character object
- **AND** event.context does NOT contain destination_description

#### Scenario: Map transition without companions
- **WHEN** player travels alone from Jupiter to Zaton
- **THEN** event.context.source equals "jupiter"
- **AND** event.context.destination equals "zaton"
- **AND** event.context.companions is empty array

#### Scenario: First visit to location
- **WHEN** player visits a location for the first time
- **THEN** event.context.visit_count equals 1

#### Scenario: Subsequent visit to location
- **WHEN** player visits a location they've been to 3 times before
- **THEN** event.context.visit_count equals 4
