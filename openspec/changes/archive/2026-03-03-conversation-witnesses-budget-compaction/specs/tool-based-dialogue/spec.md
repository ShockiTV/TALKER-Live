# tool-based-dialogue (delta)

## MODIFIED Requirements

### Requirement: ConversationManager class

The system SHALL provide a `ConversationManager` class that maintains a conversation (system prompt + messages list) per session. It SHALL be the sole dialogue generation path, replacing `DialogueGenerator` and `SpeakerSelector`. After dialogue generation completes, it SHALL trigger witness event injection for all alive candidates and delegate compaction scheduling to `CompactionScheduler` instead of directly spawning per-character compaction tasks.

#### Scenario: ConversationManager replaces DialogueGenerator
- **WHEN** a game event triggers dialogue generation
- **THEN** `ConversationManager` SHALL handle the full flow: event formatting, LLM call with tools, response extraction

#### Scenario: ConversationManager created per session
- **WHEN** a new session connects
- **THEN** a `ConversationManager` SHALL be created with the session's config
- **AND** it SHALL maintain its own message history

#### Scenario: Post-dialogue witness injection
- **WHEN** `handle_event()` returns a speaker_id and dialogue_text
- **THEN** witness events SHALL be injected for all alive candidates via `_inject_witness_events()`
- **AND** `CompactionScheduler.schedule()` SHALL be called with all candidate character IDs

#### Scenario: _characters_touched set removed
- **WHEN** the tool loop executes tool calls
- **THEN** individual character IDs SHALL NOT be tracked in a `_characters_touched` set
- **AND** compaction scheduling SHALL use the full candidates list instead

## REMOVED Requirements

### Requirement: Per-character compaction task creation in post-dialogue
**Reason**: Replaced by `CompactionScheduler` budget-pool mechanism. The old unbounded `create_compaction_task()` loop in the post-dialogue block is removed.
**Migration**: Use `CompactionScheduler.schedule(candidate_ids)` after dialogue generation.
