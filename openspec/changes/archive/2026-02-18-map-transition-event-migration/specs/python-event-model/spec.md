# python-event-model (delta)

## ADDED Requirements

### Requirement: MAP_TRANSITION Event Formatting

The `describe_event()` function SHALL format MAP_TRANSITION events with location names, visit count, companions, and destination description.

Output format: `"{actor} [and their travelling companions {companions}] traveled from {source_name} to {destination_name} {visit_text}. {destination_description}"`

Components:
- `source_name`: Human-readable name resolved from `context.source` technical ID
- `destination_name`: Human-readable name resolved from `context.destination` technical ID
- `visit_text`: "for the first time" (visit_count=1), "for the 2nd time" (2), "for the 3rd time" (3), "again" (>3)
- `companions`: Comma-separated names with "and" before last (e.g., "Hip and Fanatic")
- `destination_description`: Full description from `get_location_description()`

#### Scenario: Solo travel first visit
- **WHEN** describe_event() is called on MAP_TRANSITION event
- **AND** context.source is "l01_escape"
- **AND** context.destination is "l02_garbage"
- **AND** context.visit_count is 1
- **AND** context.companions is empty
- **THEN** result contains "traveled from Cordon to Garbage for the first time"
- **AND** result contains Garbage's location description

#### Scenario: Travel with one companion
- **WHEN** describe_event() is called on MAP_TRANSITION event
- **AND** context.companions contains one Character named "Hip"
- **THEN** result contains "and their travelling companions Hip traveled from"

#### Scenario: Travel with multiple companions
- **WHEN** describe_event() is called on MAP_TRANSITION event
- **AND** context.companions contains Characters named "Hip" and "Fanatic"
- **THEN** result contains "and their travelling companions Hip and Fanatic traveled from"

#### Scenario: Subsequent visits use ordinal text
- **WHEN** context.visit_count is 2
- **THEN** result contains "for the 2nd time"
- **WHEN** context.visit_count is 3
- **THEN** result contains "for the 3rd time"

#### Scenario: Many visits use "again"
- **WHEN** context.visit_count is greater than 3
- **THEN** result contains "again"

#### Scenario: Unknown location ID falls back gracefully
- **WHEN** context.destination is "unknown_level_id"
- **THEN** result uses "unknown_level_id" as destination name
- **AND** destination description is omitted

### Requirement: Location Description Lookup

The `get_location_description()` function SHALL return detailed location descriptions.

#### Scenario: Known location returns description
- **WHEN** get_location_description("l02_garbage") is called
- **THEN** returns description containing "Garbage" and relevant details

#### Scenario: Unknown location returns empty string
- **WHEN** get_location_description("unknown_id") is called
- **THEN** returns empty string
