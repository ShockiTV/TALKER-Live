# witness-event-injection

**Status:** delta  
**Change:** deduplicated-prompt-architecture

## MODIFIED Requirements

### Requirement: Witness event text format

Each injected witness event SHALL contain a short templated description built from the event's type and context fields. The witness list (name + ID pairs) SHALL be included in the event text. The text SHALL NOT include the LLM-generated dialogue.

#### Scenario: Death event witness text with witness list
- **WHEN** injecting a witness event for a DEATH event where Wolf killed Bandit_7
- **AND** witnesses are Wolf(12467), Fanatic(34521), and Loner_42(78900)
- **THEN** the event text SHALL be `"Witnessed: DEATH — Wolf killed Bandit_7\nWitnesses: Wolf(12467), Fanatic(34521), Loner_42(78900)"`

#### Scenario: Idle event witness text
- **WHEN** injecting a witness event for an IDLE event with actor Fanatic
- **THEN** the event text SHALL be `"Witnessed: IDLE — Fanatic"` followed by the witness list

#### Scenario: Event type normalised to uppercase
- **WHEN** the event type is `"death"` (lowercase from Lua wire format)
- **THEN** the witness text SHALL normalise it to `"DEATH"`

## ADDED Requirements

### Requirement: Events injected as shared system messages with witnesses

When an event is processed by the `ConversationManager`, it SHALL be injected as a single `EVT:{ts}` system message containing the event description AND the full witness list. This replaces per-candidate event fan-out in the prompt.

#### Scenario: Event system message includes all witnesses
- **WHEN** a DEATH event with 4 witnesses is processed
- **THEN** a single system message SHALL be created: `EVT:{ts} — DEATH: Wolf killed Bandit_7\nWitnesses: Wolf(12467), Fanatic(34521), Loner_42(78900), Stalker_5(11111)`
- **AND** the dedup tracker SHALL mark the timestamp as injected

#### Scenario: Duplicate event is not re-injected
- **WHEN** a second event arrives with the same `game_time_ms` (already injected)
- **THEN** the dedup tracker SHALL report it as already injected
- **AND** no new system message SHALL be created

### Requirement: Witness list format in system messages

The witness list in event system messages SHALL use the format `Name(id)` separated by commas, appearing after the event description on a new line.

#### Scenario: Multiple witnesses formatted
- **WHEN** an event has witnesses Wolf(12467) and Fanatic(34521)
- **THEN** the witness line SHALL be `Witnesses: Wolf(12467), Fanatic(34521)`

#### Scenario: Single witness
- **WHEN** an event has only one witness
- **THEN** the witness line SHALL still be present with the single entry
