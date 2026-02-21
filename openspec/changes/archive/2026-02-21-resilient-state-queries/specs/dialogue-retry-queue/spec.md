# dialogue-retry-queue

## Purpose

Queue for parking and retrying dialogue generation requests that failed due to transient state query timeouts (Lua unresponsive during menu pause), with heartbeat-aware flush and configurable retry policy.

## ADDED Requirements

### Requirement: Retry queue stores failed dialogue requests

The system SHALL provide a `DialogueRetryQueue` class that accepts and stores dialogue generation requests that failed due to `StateQueryTimeout`. Each queued item SHALL include the event dict, generation method identifier ("event" or "instruction"), optional speaker_id, attempt count, and enqueue timestamp.

#### Scenario: Event-triggered dialogue deferred to queue
- **WHEN** `_generate_dialogue_for_speaker()` fails with `StateQueryTimeout`
- **THEN** the event dict and method ("event") SHALL be enqueued to the retry queue
- **AND** attempt count SHALL be set to 1

#### Scenario: Instruction-triggered dialogue deferred to queue
- **WHEN** `generate_from_instruction()` fails with `StateQueryTimeout`
- **THEN** the event dict, speaker_id, and method ("instruction") SHALL be enqueued
- **AND** attempt count SHALL be set to 1

### Requirement: Heartbeat-aware flush re-submits queued requests

The system SHALL flush the retry queue when a heartbeat arrives after a connectivity gap. A gap is detected when the time since the last heartbeat exceeds 2x the heartbeat interval. Flush SHALL drain all items and re-submit them as `asyncio.create_task()` calls to the dialogue generator.

#### Scenario: Flush triggered by heartbeat after gap
- **WHEN** heartbeat arrives and time since previous heartbeat >= 2x heartbeat interval
- **THEN** all queued items SHALL be re-submitted to the dialogue generator
- **AND** the queue SHALL be empty after flush

#### Scenario: Normal heartbeat does not trigger flush
- **WHEN** heartbeat arrives within normal interval (no gap detected)
- **THEN** flush SHALL NOT be triggered
- **AND** queued items SHALL remain in the queue

### Requirement: Bounded retry count prevents infinite loops

The system SHALL enforce a maximum retry count (default 5) per queued item. Items exceeding the limit SHALL be discarded during flush with a warning log. There SHALL be no time-based expiry — game time does not advance during menu pause, so all queued events remain valid regardless of wall-clock duration. There SHALL be no queue size limit — the queue is naturally bounded because Lua stops sending events while paused.

#### Scenario: Item exceeds max retries
- **WHEN** a queued item has attempt_count >= max_retries during flush
- **THEN** the item SHALL be discarded
- **AND** a warning SHALL be logged with the event type and attempt count

#### Scenario: Items survive long pause
- **WHEN** the player pauses for an extended period (minutes)
- **THEN** all queued items SHALL still be retried when Lua resumes
- **AND** no items SHALL be discarded due to wall-clock time elapsed

### Requirement: Flush is atomic with respect to concurrent access

The system SHALL drain the queue atomically during flush so that concurrent flush calls or enqueue operations do not cause duplicate processing.

#### Scenario: Concurrent flush calls
- **WHEN** two flush operations are triggered simultaneously
- **THEN** each queued item SHALL be processed exactly once
- **AND** no items SHALL be duplicated or lost
