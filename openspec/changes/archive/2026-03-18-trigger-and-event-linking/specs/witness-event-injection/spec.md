# witness-event-injection (Delta)

> **Change**: `trigger-and-event-linking`
> **Operation**: MODIFIED

---

## MODIFIED Requirements

### Requirement: Event injection is per-step filtered, not global

Event injection SHALL be filtered per step. The picker step sees the union of all candidates' events; the dialogue step sees only the chosen speaker's events.

#### Scenario: Picker step — all candidates' events (union)

- **WHEN** the picker step builds its prompt
- **THEN** it SHALL include the unified deduplicated event list from ALL candidates
- **AND** each event line SHALL include witness annotations showing which candidates saw it
- **AND** the triggering event SHALL appear in the list (identified by its `ts`)

#### Scenario: Dialogue step — speaker-filtered events

- **WHEN** the dialogue step builds its prompt for speaker S
- **THEN** it SHALL include only the events where S is a witness
- **AND** events where S is NOT a witness SHALL be excluded
- **AND** witness annotations SHALL still list all witnesses (not just S)

---

### Requirement: Events are ephemeral per-turn content

Events SHALL be included inline in the per-turn user message (Layer 4). They are NOT added to the `ContextBlock` and are NOT deduplicated across turns.

#### Scenario: Events not in context block

- **WHEN** events are rendered for a dialogue turn
- **THEN** they SHALL appear in the user message at index 3+ (Layer 4)
- **AND** they SHALL NOT appear in `_messages[1]` (the context block)

#### Scenario: Dialogue user message is ephemeral

- **WHEN** the dialogue step completes an LLM call
- **THEN** the user message (containing the event list) SHALL be removed from `_messages`
- **AND** only the assistant response SHALL persist in `_messages`

---

### Requirement: Speaker witness filter function

A helper function SHALL filter events by speaker witness status.

#### Scenario: Filter events for a specific speaker

- **WHEN** `filter_events_for_speaker(events, speaker_id)` is called with the deduplicated event collection
- **THEN** it SHALL return only events where `speaker_id` is in the event's witness list

---

## ADDED Requirements

### Requirement: Events fetched for all candidates before picker

Witness events SHALL be fetched for ALL speaker candidates in a single batch query BEFORE the picker step runs.

#### Scenario: Events batch precedes picker

- **WHEN** `handle_event()` prepares to run the speaker picker
- **THEN** it SHALL first issue a batch state query for `query.memory.events` for each candidate
- **AND** the result SHALL be available to both the picker and dialogue steps
- **AND** no second event fetch SHALL occur after the picker selects a speaker

### Requirement: Event wire format includes ts

Events received from the Lua `game.event` topic SHALL include the `ts` field (unique timestamp) in their payload.

#### Scenario: Triggering event has ts in payload

- **WHEN** Python receives a `game.event` message
- **THEN** the event object in the payload SHALL include a `ts` field with the event's unique timestamp
- **AND** this `ts` SHALL match the `ts` stored in witness memories for the same event
