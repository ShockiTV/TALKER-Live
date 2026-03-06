## ADDED Requirements

### Requirement: Per-session memory injection tracking

The `ConversationManager` SHALL maintain a `dict[str, int]` mapping `character_id → last_injected_timestamp` per session, tracking what memory state has been presented to the LLM for each character.

#### Scenario: Tracking dict initialized empty
- **WHEN** a new `ConversationManager` is created for a session
- **THEN** the memory tracking dict SHALL be empty

#### Scenario: Tracking updated after injection
- **WHEN** memories are injected for character "12467" with latest timestamp 42100
- **THEN** the tracking dict SHALL store `{"12467": 42100}`

### Requirement: Full memory injection for first-time speakers

When a character speaks for the first time in a session (no entry in the tracking dict), the system SHALL inject their full memory dump across all tiers.

#### Scenario: First-time speaker gets full memory
- **WHEN** character "12467" is chosen as speaker for the first time in this session
- **AND** "12467" has no entry in the memory tracking dict
- **THEN** the system SHALL fetch all memory tiers (events, summaries, digests, cores) for "12467"
- **AND** SHALL inject the full formatted result as part of the dialogue user message

#### Scenario: Full memory includes background
- **WHEN** full memory is injected for a first-time speaker
- **THEN** the injection SHALL include the character's background (traits, backstory, connections) in addition to memory tiers

### Requirement: Diff memory injection for returning speakers

When a character speaks again in the same session (has an entry in the tracking dict), the system SHALL inject only memories newer than the last-seen timestamp.

#### Scenario: Returning speaker gets diff only
- **WHEN** character "12467" speaks again and their last_injected_timestamp is 42100
- **THEN** the system SHALL fetch only events with timestamp > 42100
- **AND** SHALL inject only the new events as part of the dialogue user message
- **AND** SHALL include a note like "Additional events since last time you spoke:"

#### Scenario: No new memories since last injection
- **WHEN** character "12467" speaks again but has no new memories since timestamp 42100
- **THEN** the memory section of the dialogue user message SHALL indicate "No new memories since your last dialogue"
- **AND** the LLM SHALL rely on conversation history for existing context

### Requirement: Timestamp extracted from memory data

The system SHALL determine the latest timestamp from injected memory data to update the tracking dict.

#### Scenario: Timestamp from events tier
- **WHEN** memory data is fetched and events tier contains entries with timestamps
- **THEN** the latest timestamp across all returned entries SHALL be used to update the tracking dict

#### Scenario: No timestamp available
- **WHEN** memory data is fetched but contains no entries with timestamps
- **THEN** the tracking dict SHALL store 0 as the timestamp
- **AND** the next injection SHALL fetch all memories again (effectively a full refresh)
