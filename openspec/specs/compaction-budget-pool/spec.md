# compaction-budget-pool

## Purpose

Shared budget-pool scheduler that limits the total number of compaction LLM calls per dialogue cycle across all characters, prioritising characters with the most over-cap memory tiers.

## Requirements

### Requirement: CompactionScheduler class

The system SHALL provide a `CompactionScheduler` class in `memory/scheduler.py` that accepts a `CompactionEngine` reference and a budget constant. It SHALL be the sole entry point for post-dialogue compaction scheduling, replacing direct per-character `create_compaction_task()` calls.

#### Scenario: Scheduler created with budget
- **WHEN** `CompactionScheduler(engine, budget=3)` is constructed
- **THEN** it SHALL store the engine reference and budget limit

#### Scenario: Scheduler replaces direct task creation
- **WHEN** dialogue generation completes
- **THEN** `CompactionScheduler.schedule(character_ids)` SHALL be called instead of looping `create_compaction_task()` per character

### Requirement: Budget limits total LLM calls

The scheduler SHALL run compaction for at most `COMPACTION_BUDGET` characters per scheduling call (default 3). Characters beyond the budget SHALL be logged as deferred and skipped.

#### Scenario: 8 witnesses, budget 3
- **WHEN** `schedule([c1, c2, ..., c8])` is called with budget 3
- **THEN** compaction SHALL run for the top 3 characters by priority score
- **AND** the remaining 5 SHALL be logged as deferred

#### Scenario: 2 witnesses, budget 3
- **WHEN** `schedule([c1, c2])` is called with budget 3
- **THEN** compaction SHALL run for both characters (budget not exhausted)

#### Scenario: Budget of 0 disables compaction
- **WHEN** `schedule(ids)` is called with budget 0
- **THEN** no compaction SHALL run
- **AND** all characters SHALL be logged as deferred

### Requirement: Priority scoring by tier bloat

The scheduler SHALL query `npc.memories.tiers` for all candidate characters in a single batch query, then compute a priority score for each character as the sum of `max(0, count - cap)` across all four tiers. Characters SHALL be sorted by score descending (highest bloat first).

#### Scenario: Character with over-cap events ranks higher
- **WHEN** character A has events=120 (cap 100, excess 20) and character B has events=50
- **THEN** character A SHALL have a higher priority score than character B

#### Scenario: Multiple tiers contribute to score
- **WHEN** character C has events=110 (excess 10) and summaries=12 (excess 2)
- **THEN** character C's score SHALL be 12 (10 + 2)

#### Scenario: Character at or below all caps scores zero
- **WHEN** character D has events=50, summaries=5, digests=3, cores=2
- **THEN** character D's score SHALL be 0
- **AND** character D SHALL NOT be scheduled for compaction

#### Scenario: Zero-score characters skipped entirely
- **WHEN** all characters score 0 (no tiers over cap)
- **THEN** no compaction SHALL run (budget not consumed)

### Requirement: Single batch query for scoring

Tier counts for all candidate characters SHALL be fetched in one `state.query.batch` call containing one `npc.memories.tiers` sub-query per character.

#### Scenario: 5 candidates scored in one roundtrip
- **WHEN** `schedule([c1, c2, c3, c4, c5])` is called
- **THEN** a single `state.query.batch` SHALL be sent with 5 `npc.memories.tiers` sub-queries

#### Scenario: Batch query failure skips scheduling
- **WHEN** the tier count batch query fails
- **THEN** scheduling SHALL log a warning and skip compaction for this cycle

### Requirement: Scheduler runs as background task

The scheduler SHALL run as a single `asyncio.Task` to avoid blocking the dialogue response path. Within that task, compaction for each selected character SHALL be awaited serially to respect the `CompactionEngine._active_compactions` guard.

#### Scenario: Non-blocking scheduling
- **WHEN** `schedule()` is called
- **THEN** it SHALL return immediately (creating a background task)
- **AND** dialogue display SHALL NOT wait for compaction to complete

#### Scenario: Serial execution within budget
- **WHEN** the budget selects characters [c1, c2, c3]
- **THEN** `check_and_compact(c1)` SHALL complete before `check_and_compact(c2)` starts
