# task-giver-in-prompt

## Purpose

Ensures the task giver character is correctly serialized over the wire and rendered in Python TASK event descriptions.

## Requirements

### Requirement: task_giver faction sent as technical ID

The Lua TASK trigger SHALL send `task_giver.faction` as a technical faction ID (e.g. `"dolg"`, `"killer"`, `"stalker"`) rather than a display name. Python's `resolve_faction_name()` is responsible for converting to display names.

#### Scenario: task_giver faction is technical ID on wire
- **WHEN** a TASK event is created with a task giver from the Duty faction
- **THEN** `task_giver.faction` in the ZMQ payload SHALL be `"dolg"`, not `"Duty"`

### Requirement: task_giver serialized as Character

The ZMQ serializer SHALL treat `"task_giver"` as a recognized character key in `serialize_context()`, normalizing it through `serialize_character()` the same way as `"actor"`, `"victim"`, etc.

#### Scenario: task_giver passes through serialize_character
- **WHEN** a context table with a `task_giver` key is serialized
- **THEN** the resulting dict SHALL have `task_giver.game_id` as a string
- **THEN** all character fields (name, faction, experience, reputation, weapon, visual_faction) SHALL be preserved

#### Scenario: nil task_giver is handled gracefully
- **WHEN** a context table has no `task_giver` key
- **THEN** serialization SHALL succeed without error and `task_giver` SHALL be absent from the result

### Requirement: task_giver rendered in TASK event description

The Python `describe_event()` helper SHALL include the task giver in the TASK event description string when the `task_giver` character is present in the event context.

#### Scenario: TASK description includes task giver
- **WHEN** `describe_event()` is called with a TASK event containing a `task_giver` character
- **THEN** the returned string SHALL include the task giver's name and faction

#### Scenario: TASK description without task giver
- **WHEN** `describe_event()` is called with a TASK event that has no `task_giver`
- **THEN** the returned string SHALL still include actor and task name, without error
