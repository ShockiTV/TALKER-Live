# memory-diff-injection

## Purpose

Defines per-session memory injection tracking for dialogue generation using a `DeduplicationTracker` that tracks individual injected items (events, backgrounds, memories) as sets. First-time speakers receive full memory system messages, returning speakers receive only new items not yet in the tracker.

## Requirements

### Requirement: Per-session memory injection tracking

The `ConversationManager` SHALL maintain a `DeduplicationTracker` that tracks injected events, backgrounds, and memories as three separate sets per session. This replaces the `dict[str, int]` mapping of `character_id → last_injected_timestamp`.

#### Scenario: Tracking initialized empty
- **WHEN** a new `ConversationManager` is created for a session
- **THEN** the `DeduplicationTracker` SHALL have all three sets empty

#### Scenario: Tracking updated after injection
- **WHEN** a memory item for character "12467" with `start_ts=42100` is injected as a system message
- **THEN** the tracker SHALL store `(12467, 42100)` in its memory set

### Requirement: Full memory injection for first-time speakers

When a character speaks for the first time in a session, the system SHALL inject their compacted memories (summaries, digests, cores) as individual `MEM:{char_id}:{start_ts}` system messages, and include personal narrative text in the dialogue user message.

#### Scenario: First-time speaker gets memory system messages
- **WHEN** character "12467" is chosen as speaker for the first time in this session
- **AND** "12467" has no memory entries in the dedup tracker
- **THEN** the system SHALL inject each compacted memory as a separate `MEM:12467:{start_ts}` system message
- **AND** the dedup tracker SHALL mark each (char_id, start_ts) pair as injected

#### Scenario: First-time speaker background NOT re-injected
- **WHEN** full memories are injected for a first-time speaker
- **AND** the speaker's background is already present as a `BG:{char_id}` system message (from the picker step)
- **THEN** the background SHALL NOT be injected again

### Requirement: Diff memory injection for returning speakers

When a character speaks again in the same session, the system SHALL inject only memory items whose (char_id, start_ts) pairs are NOT in the dedup tracker.

#### Scenario: Returning speaker gets new memories only
- **WHEN** character "12467" speaks again and some memory items are already tracked
- **THEN** only memory items with untracked (char_id, start_ts) pairs SHALL be injected as new system messages
- **AND** the dialogue user message SHALL include updated personal narrative text

#### Scenario: No new memories since last injection
- **WHEN** character "12467" speaks again but all memory items are already tracked
- **THEN** no new `MEM:` system messages SHALL be injected
- **AND** the dialogue user message SHALL indicate "No new memories since your last dialogue"

### Requirement: Tracker resilient to pruning

After message window pruning removes system messages, the dedup tracker SHALL rebuild its state from surviving messages.

#### Scenario: Pruning removes old memory system messages
- **WHEN** the message window is pruned and some `MEM:` system messages are removed
- **THEN** `rebuild_from_messages()` SHALL be called
- **AND** the tracker SHALL only contain entries for surviving system messages
- **AND** subsequent memory injection SHALL re-inject previously pruned items if the character speaks again
