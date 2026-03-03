## Why

When a game event triggers dialogue, the Lua side sends all nearby NPC candidates. The LLM picks one speaker and may tool-call `get_memories` / `background` for a few characters — only those "touched" characters get post-dialogue compaction scheduled. **Witnesses who were not queried accumulate no memory of the event and never get compacted**, even though they were present. Over time this means most NPCs have no recall of events they saw, and the few who _are_ queried can pile up many uncompacted events before the next check. A companion who watched a combat but was not the speaker will never remember that fight.

Additionally, compaction scheduling is currently unbounded: every touched character spawns its own `asyncio.Task`, each potentially making multiple LLM calls across tiers. After a busy firefight with many witnesses, the system could launch dozens of concurrent compaction calls, spiking API costs and latency with no throttling.

## What Changes

- **Witness event injection**: After dialogue generation completes, store the triggering event in the `events` tier of every candidate who witnessed it (not just the speaker or tool-queried characters). This uses existing `state.mutate.batch` to append one event per witness in a single roundtrip.
- **Budget-pool compaction scheduler**: Replace the current unbounded per-character `create_compaction_task()` loop with a budget-pool mechanism. A fixed budget of N compaction LLM calls (configurable, default 3) is shared across all characters that need compaction after a dialogue cycle. Characters are prioritised by tier bloat (highest over-cap first), and excess characters are deferred to the next cycle.
- **Compaction priority scoring**: Add a lightweight scoring function in `CompactionEngine` that computes how over-cap each character's tiers are, so the budget-pool can rank them.

## Capabilities

### New Capabilities
- `witness-event-injection`: Store the triggering event in every witness candidate's events tier after dialogue, ensuring all nearby NPCs remember what they saw.
- `compaction-budget-pool`: Shared budget-pool scheduler that limits total compaction LLM calls per dialogue cycle and prioritises characters by tier bloat.

### Modified Capabilities
- `compaction-cascade`: Add priority-scoring method and accept optional call-budget parameter so the cascade can be terminated early when the pool is exhausted.
- `tool-based-dialogue`: Post-dialogue hook changes from unbounded per-character task creation to witness injection + budget-pool scheduling.

## Impact

- **Python `dialogue/conversation.py`**: Post-dialogue block (lines ~736–744) replaced with witness injection + budget-pool call.
- **Python `memory/compaction.py`**: New `score_character()` method; `check_and_compact()` gains optional `budget` parameter to cap LLM calls.
- **New module `memory/scheduler.py`**: Budget-pool scheduler that accepts a set of character IDs, scores them, and runs compaction within a shared budget.
- **Wire protocol**: New `state.mutate.batch` usage pattern (batch append of events for multiple characters in one roundtrip) — uses existing mutation verbs, no protocol changes.
- **Lua `memory_store_v2`**: No changes — events are appended via the existing `append` mutation handler.
- **LLM cost**: Witness injection adds zero LLM calls (pure state mutation). Budget-pool _reduces_ peak LLM calls by capping concurrent compaction.
