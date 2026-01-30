## ADDED Requirements

### Requirement: Three-tier memory architecture
The system SHALL maintain NPC memories in three tiers: recent events (raw), mid-term memory (compressed summary), and long-term narrative (incrementally updated).

#### Scenario: Memory context retrieval
- **WHEN** dialogue generation requests memory context for a character
- **THEN** system returns narrative (if exists), last_update_time_ms, and new_events since last compression

### Requirement: Threshold-based compression trigger
The system SHALL trigger memory compression when a character's unprocessed events reach or exceed COMPRESSION_THRESHOLD (12 events).

#### Scenario: Compression triggered at threshold
- **WHEN** character has 12 or more unprocessed events
- **THEN** system initiates memory compression in background

#### Scenario: No compression below threshold
- **WHEN** character has fewer than 12 unprocessed events
- **THEN** system skips compression and uses events directly

### Requirement: Bootstrap compression for new memories
The system SHALL use create_compress_memories_prompt() when no existing narrative exists, producing a single paragraph under 900 characters.

#### Scenario: First compression for character
- **WHEN** compression triggers and character has no existing narrative
- **THEN** system generates mid-term summary from raw events

### Requirement: Incremental narrative update
The system SHALL use create_update_narrative_prompt() to merge new events into existing narrative, detecting and handling overlaps.

#### Scenario: Update existing narrative
- **WHEN** compression triggers and character has existing narrative
- **THEN** system merges new events into narrative, handling overlaps

#### Scenario: Narrative length management
- **WHEN** narrative exceeds 5500 characters before update
- **THEN** system condenses existing narrative before integrating new events

### Requirement: Narrative character limit
The system SHALL enforce a maximum of 6400 characters for long-term narrative output.

#### Scenario: Output exceeds limit
- **WHEN** generated narrative exceeds 6400 characters
- **THEN** LLM is instructed to aggressively compress to fit limit

### Requirement: Non-blocking compression
The system SHALL execute compression as a background task without blocking dialogue generation.

#### Scenario: Dialogue generation during compression
- **WHEN** compression is in progress for a character
- **THEN** dialogue generation proceeds with current memory state

### Requirement: Per-character concurrency control
The system SHALL use per-character locks to prevent concurrent compression operations for the same character.

#### Scenario: Concurrent compression attempts
- **WHEN** compression is already in progress for a character
- **THEN** subsequent compression requests are skipped (non-blocking check)

### Requirement: Memory update via ZMQ command
The system SHALL publish memory.update command to Lua after successful compression.

#### Scenario: Successful compression update
- **WHEN** LLM generates valid narrative
- **THEN** system publishes memory.update with character_id, narrative, and last_event_time_ms

### Requirement: Lua memory store update
The Lua memory_store SHALL update narrative_memories when receiving memory.update command.

#### Scenario: Narrative update applied
- **WHEN** Lua receives memory.update command
- **THEN** memory_store updates character's narrative and last_update_time_ms

### Requirement: Junk event filtering
The system SHALL filter out junk events (artifacts, anomalies, reloads, weapon jams) from compression prompts.

#### Scenario: Junk events excluded
- **WHEN** building compression prompt
- **THEN** events with type ARTIFACT, ANOMALY, RELOAD, WEAPON_JAM are excluded

### Requirement: Chronological ordering
The system SHALL preserve exact chronological order of events in compressed narratives.

#### Scenario: Events ordered by timestamp
- **WHEN** events are processed for compression
- **THEN** events are sorted by game_time_ms ascending

### Requirement: Third-person perspective
The system SHALL generate narratives in third person, referring to the character by name.

#### Scenario: Narrative perspective
- **WHEN** generating or updating narrative
- **THEN** output uses third-person perspective with character's name

### Requirement: Save format persistence
The system SHALL persist narrative_memories with narrative and last_update_time_ms per character.

#### Scenario: Save game with memories
- **WHEN** game saves state
- **THEN** narrative_memories map is persisted with all character data

### Requirement: Legacy format migration
The system SHALL migrate old array-based memory format to new narrative structure on load.

#### Scenario: Load legacy save with array format
- **WHEN** loading save with old array-based memories
- **THEN** system migrates to new format, triggering compression if threshold exceeded
