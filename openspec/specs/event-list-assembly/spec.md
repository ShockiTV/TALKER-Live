# event-list-assembly

## Purpose

Fetches witness events for all speaker candidates, deduplicates across candidates by `ts` timestamp, and formats a unified event list with `[ts]` identifiers and witness annotations. Provides building blocks for both the picker and dialogue steps.

## Requirements

### Requirement: Fetch events for all candidates in one batch

The system SHALL fetch witness events for all speaker candidates in a single batch state query before the picker step.

#### Scenario: Batch query for 4 candidates
- **WHEN** `handle_event()` has 4 speaker candidates
- **THEN** the system SHALL issue one `state.query.batch` with 4 `query.memory.events` sub-queries (one per candidate)
- **AND** the batch SHALL be issued before the picker step runs
- **AND** the result SHALL be a mapping of `candidate_id → [event_dict, ...]`

#### Scenario: Candidate with no stored events
- **WHEN** a candidate has zero events in their memory
- **THEN** their entry in the result mapping SHALL be an empty list
- **AND** the remaining candidates' events SHALL still be included

#### Scenario: Batch query timeout
- **WHEN** the batch state query times out
- **THEN** the system SHALL proceed with empty event lists for all candidates
- **AND** dialogue generation SHALL NOT be blocked

### Requirement: Deduplicate events across candidates by ts

The system SHALL deduplicate events from all candidates into a single unique-events collection keyed by `ts`.

#### Scenario: Same event witnessed by 3 candidates
- **WHEN** candidates A, B, and C all have an event with `ts=1709912345`
- **THEN** the deduplicated collection SHALL contain exactly one entry for `ts=1709912345`
- **AND** the witness map for that `ts` SHALL contain the names of A, B, and C

#### Scenario: Events unique to one candidate
- **WHEN** candidate A has an event with `ts=1709912001` that no other candidate has
- **THEN** the deduplicated collection SHALL contain that event
- **AND** its witness set SHALL contain only A's name

### Requirement: Format event line with ts and witness annotations

The system SHALL provide a `format_event_line(ts, event, witness_names)` function that renders a single event as a one-line string.

#### Scenario: Death event with two witnesses
- **WHEN** formatting event `{type: "DEATH", context: {actor: "Freedom Soldier", victim: "Monolith Fighter"}}` with `ts=1709912001` and witnesses `{"Echo", "Wolf"}`
- **THEN** the output SHALL be `[1709912001] DEATH — Freedom Soldier killed Monolith Fighter (witnesses: Echo, Wolf)`

#### Scenario: Event with one witness
- **WHEN** formatting an event with only one witness name `{"Echo"}`
- **THEN** the witnesses annotation SHALL read `(witnesses: Echo)`

### Requirement: Build full event list text

The system SHALL provide a function that takes the deduplicated events and witness map and produces a multi-line text block sorted by `ts` ascending.

#### Scenario: Three events sorted by timestamp
- **WHEN** building the event list from events with `ts` values `[1709912345, 1709912001, 1709912078]`
- **THEN** the output SHALL list events in ascending `ts` order: `1709912001`, `1709912078`, `1709912345`
- **AND** each line SHALL use the `format_event_line` format

### Requirement: Filter events for a specific speaker

The system SHALL provide a function that filters the deduplicated events to only those witnessed by a given speaker.

#### Scenario: Speaker witnessed 2 of 5 events
- **WHEN** filtering for speaker "Echo" and the witness map shows Echo in 2 of 5 events
- **THEN** the filtered result SHALL contain exactly those 2 events
- **AND** witness annotations SHALL still include all witnesses (not just the speaker)
