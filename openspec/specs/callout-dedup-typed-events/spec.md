# callout-dedup-typed-events

## Purpose

Defines typed event deduplication and callout trigger behavior to prevent duplicate events from the same source.

## Requirements

### Requirement: Typed event dedup matching

The callout anti-spam logic in `talker_trigger_callout.script` SHALL match recent events using typed event fields instead of the legacy `event.description` string. Specifically, it SHALL check:

1. `event.type == EventType.CALLOUT`
2. `event.context.target.name == target_name` (the current callout target)

This replaces the broken `string.find(event.description, ...)` pattern, which silently fails because typed events have no `description` field.

#### Scenario: Duplicate callout for same target suppressed

- **WHEN** a CALLOUT event for target `"bandit_01"` already exists in recent events within the cooldown window
- **AND** a new callout fires for the same target `"bandit_01"`
- **THEN** the new callout SHALL be suppressed by the anti-spam logic

#### Scenario: Callout for different target allowed

- **WHEN** a CALLOUT event for target `"bandit_01"` exists in recent events
- **AND** a new callout fires for a different target `"military_03"`
- **THEN** the new callout SHALL NOT be suppressed

#### Scenario: No recent callout allows new callout

- **WHEN** no CALLOUT events exist in recent events (or all are outside the cooldown window)
- **AND** a new callout fires for target `"bandit_01"`
- **THEN** the callout SHALL proceed normally

#### Scenario: Safe traversal of event context

- **WHEN** a recent event has `type == "CALLOUT"` but `event.context` or `event.context.target` is `nil`
- **THEN** the dedup check SHALL handle the nil safely without crashing (e.g. `event.context and event.context.target and event.context.target.name`)

### Requirement: Callout flags include target_name

The callout event creation SHALL pass `target_name` in the event flags table, replacing the current empty flags `{}`. The flags SHALL include at minimum:

- `is_callout = true`
- `target_name = <enemy_name>`

This enables downstream consumers (Python service, other triggers) to identify callout events and their targets without parsing context.

#### Scenario: Callout event includes target in flags

- **WHEN** an NPC spots enemy `"bandit_leader"` and a callout event is created
- **THEN** the event's flags table SHALL contain `is_callout = true` and `target_name = "bandit_leader"`

#### Scenario: Flags preserved through serialization

- **WHEN** a callout event with `flags.target_name = "bandit_leader"` is serialized for ZMQ transmission
- **THEN** the `target_name` field SHALL be present in the serialized JSON payload
