# compaction-cascade (delta)

## MODIFIED Requirements

### Requirement: Compaction trigger

Compaction SHALL be triggered per-NPC when any tier exceeds its cap. The `CompactionScheduler` SHALL be the sole caller of `check_and_compact()` after dialogue cycles. Direct `create_compaction_task()` calls from `ConversationManager` SHALL be removed.

#### Scenario: Single-tier compaction
- **WHEN** only the events tier is over cap for character 12467
- **THEN** only events→summaries compaction SHALL run for that character

#### Scenario: Multi-tier cascade
- **WHEN** compacting events to a summary causes the summaries tier to exceed its cap
- **THEN** summaries→digests compaction SHALL also run in the same cycle

#### Scenario: Compaction triggered by scheduler
- **WHEN** `CompactionScheduler.schedule(character_ids)` selects a character for compaction
- **THEN** it SHALL call `CompactionEngine.check_and_compact(character_id)`
- **AND** `create_compaction_task()` SHALL NOT be called from `ConversationManager`

## ADDED Requirements

### Requirement: Priority scoring support

`CompactionEngine` SHALL expose a `score_character(tiers: dict) -> int` static/class method that computes how over-cap a character's tiers are. The score is `sum(max(0, count - cap) for each tier)`. This method SHALL be used by `CompactionScheduler` for priority ranking.

#### Scenario: Over-cap events scored
- **WHEN** `score_character({"events": 120, "summaries": 5, "digests": 3, "cores": 2})` is called
- **THEN** the result SHALL be 20 (120 - 100)

#### Scenario: Multiple over-cap tiers summed
- **WHEN** `score_character({"events": 110, "summaries": 12, "digests": 3, "cores": 2})` is called
- **THEN** the result SHALL be 12 (10 + 2 + 0 + 0)

#### Scenario: All below cap scores zero
- **WHEN** `score_character({"events": 50, "summaries": 5, "digests": 3, "cores": 2})` is called
- **THEN** the result SHALL be 0
