# compaction-cascade

## Purpose

Four-tier LLM-driven memory compaction system that progressively compresses NPC event histories from raw events through summaries, digests, and cores.

## Requirements

### Requirement: Four-tier compaction flow

The compaction system SHALL compress memory in a cascade: events(10) → 1 summary, summaries(2) → 1 digest, digests(2) → 1 core, cores(2) → 1 core (self-compacting terminal tier).

#### Scenario: Events compacted to summary
- **WHEN** a character's events tier has more than the events cap (100)
- **THEN** the 10 oldest events (by seq) SHALL be read
- **AND** an LLM call SHALL generate a single summary from those events
- **AND** a `state.mutate.batch` SHALL delete those 10 events and append the summary

#### Scenario: Summaries compacted to digest
- **WHEN** a character's summaries tier has more than the summaries cap (10)
- **THEN** the 2 oldest summaries SHALL be read
- **AND** an LLM call SHALL merge them into a single digest
- **AND** a `state.mutate.batch` SHALL delete those 2 summaries and append the digest

#### Scenario: Digests compacted to core
- **WHEN** a character's digests tier has more than the digests cap (5)
- **THEN** the 2 oldest digests SHALL be read and merged into a single core entry

#### Scenario: Cores self-compact
- **WHEN** a character's cores tier has more than the cores cap (5)
- **THEN** the 2 oldest cores SHALL be merged into a single core entry
- **AND** the cores tier remains the terminal tier (no further compaction)

### Requirement: Compaction trigger

Compaction SHALL be triggered per-NPC when any tier exceeds its cap. The system SHALL check all tiers for the character after each mutation and cascade as needed.

#### Scenario: Single-tier compaction
- **WHEN** only the events tier is over cap for character 12467
- **THEN** only events→summaries compaction SHALL run for that character

#### Scenario: Multi-tier cascade
- **WHEN** compacting events to a summary causes the summaries tier to exceed its cap
- **THEN** summaries→digests compaction SHALL also run in the same cycle

### Requirement: Compaction uses fast model

Compaction LLM calls SHALL use `model_name_fast` (the fast/cheap model config), not the dialogue model. This is independently configurable.

#### Scenario: Fast model used for compaction
- **WHEN** compaction runs
- **THEN** the LLM call SHALL use the `model_name_fast` client, not the primary dialogue model

### Requirement: Atomic delete+append pattern

Each compaction step SHALL use the atomic pattern: read items with IDs → LLM compress → delete by those exact IDs + append result. This eliminates TOCTOU race conditions.

#### Scenario: New events during compaction are safe
- **WHEN** Python reads events [seq 1-10] for compaction
- **AND** Lua appends event [seq 11] during the LLM call
- **THEN** the delete SHALL only remove seq 1-10
- **AND** event seq 11 SHALL remain untouched

#### Scenario: Stale IDs silently skipped
- **WHEN** an event was already deleted (e.g., by a concurrent compaction)
- **THEN** the delete for that ID SHALL be silently skipped

### Requirement: Compaction prompt format

The compaction prompt SHALL instruct the LLM to compress the source items into a single narrative summary in third person. The prompt SHALL include the character's name and the source text content.

#### Scenario: Events-to-summary prompt
- **WHEN** compacting 10 events into a summary for Wolf
- **THEN** the prompt SHALL include all 10 event texts (rendered from templates) and instruct third-person summary

#### Scenario: Summaries-to-digest prompt
- **WHEN** compacting 2 summaries into a digest
- **THEN** the prompt SHALL include both summary texts and instruct merging into a coherent narrative

### Requirement: Non-blocking compaction

Compaction SHALL run as a background asyncio task and SHALL NOT block the dialogue generation pipeline or the WS message loop.

#### Scenario: Dialogue proceeds during compaction
- **WHEN** compaction is running for a character
- **THEN** new events and dialogue generation for that character SHALL NOT be blocked

#### Scenario: Concurrent compaction prevented for same character
- **WHEN** compaction is already running for character 12467
- **THEN** a second compaction request for the same character SHALL be skipped
