# witness-event-injection

## Purpose

After dialogue generation, store the triggering game event in the `events` tier of every nearby candidate NPC, ensuring all witnesses remember what they observed — not just the speaker or characters whose tools the LLM called.

## Requirements

### Requirement: All alive candidates receive the event

After `ConversationManager.handle_event()` completes, the system SHALL append a witness event record to the `events` tier of every candidate character whose `is_alive` field is true. Dead candidates (e.g., the victim in a DEATH event) SHALL NOT receive the event.

#### Scenario: Three alive candidates witness a death
- **WHEN** a DEATH event generates dialogue with candidates [Wolf, Fanatic, Loner_42] and victim [Bandit_7]
- **AND** Wolf, Fanatic, and Loner_42 are alive; Bandit_7 is dead
- **THEN** a witness event SHALL be appended to the events tier of Wolf, Fanatic, and Loner_42
- **AND** no event SHALL be appended for Bandit_7

#### Scenario: Single candidate (speaker only)
- **WHEN** an event has exactly one alive candidate who is the speaker
- **THEN** that candidate SHALL still receive the witness event in their events tier

#### Scenario: All candidates dead or despawned
- **WHEN** all candidates have `is_alive: false`
- **THEN** no witness events SHALL be injected

### Requirement: Witness event text format

Each injected witness event SHALL contain a short templated description built from the event's type and context fields (e.g., `"Witnessed: DEATH — Wolf killed Bandit_7"`). The text SHALL NOT include the LLM-generated dialogue.

#### Scenario: Death event witness text
- **WHEN** injecting a witness event for a DEATH event where Wolf killed Bandit_7
- **THEN** the event text SHALL be `"Witnessed: DEATH — Wolf killed Bandit_7"`

#### Scenario: Idle event witness text
- **WHEN** injecting a witness event for an IDLE event with actor Fanatic
- **THEN** the event text SHALL be `"Witnessed: IDLE — Fanatic"` (no victim)

#### Scenario: Event type normalised to uppercase
- **WHEN** the event type is `"death"` (lowercase from Lua wire format)
- **THEN** the witness text SHALL normalise it to `"DEATH"`

### Requirement: Single mutate_batch roundtrip

All witness event appends for a single dialogue cycle SHALL be sent in one `state.mutate.batch` call containing one append mutation per alive candidate.

#### Scenario: Batch mutation for 5 witnesses
- **WHEN** 5 alive candidates need witness events
- **THEN** a single `state.mutate.batch` SHALL be sent with 5 append mutations
- **AND** each mutation SHALL target the candidate's `events` resource

#### Scenario: Mutation failure logged but not fatal
- **WHEN** the `state.mutate.batch` call fails (e.g., WS timeout)
- **THEN** the failure SHALL be logged as a warning
- **AND** dialogue display SHALL NOT be affected (injection is fire-and-forget)

### Requirement: Injection runs after dialogue display

Witness event injection SHALL occur after the speaker/dialogue pair is returned from `handle_event()`, so that injection failure cannot delay or block dialogue display.

#### Scenario: Dialogue displayed before injection
- **WHEN** `handle_event()` returns speaker_id and dialogue_text
- **THEN** `dialogue.display` SHALL be published first
- **AND** witness injection SHALL run afterward (may be awaited or fire-and-forget)
