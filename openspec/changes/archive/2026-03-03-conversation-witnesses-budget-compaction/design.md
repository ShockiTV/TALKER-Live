## Context

After dialogue generation the `ConversationManager` post-dialogue block (conversation.py ~L736-744) iterates `_characters_touched` — the set of character IDs whose tools the LLM called — and spawns one `create_compaction_task()` per character. This has two shortcomings:

1. **Silent witnesses are forgotten.** The `candidates` list sent from Lua contains every nearby NPC, but only those whose `get_memories` / `background` tool was invoked get tracked. A candidate who was never queried has no event stored and no compaction scheduled.
2. **Unbounded compaction fan-out.** Each character task runs `check_and_compact()` independently. In a dense area with 8+ witnesses this can produce a burst of LLM calls (up to 4 tiers × N characters) with no throttle.

The existing `state.mutate.batch` verb with `append` to the `events` resource already supports multi-character writes — Lua applies each mutation independently — so witness injection requires no wire protocol changes.

## Goals / Non-Goals

**Goals:**
- Every candidate NPC in a `game.event` payload gets the triggering event stored in their `events` tier, regardless of whether the LLM queried their tools.
- Total compaction LLM calls per dialogue cycle are bounded by a configurable budget (default 3).
- Characters with the most over-cap tiers are compacted first; the rest are deferred until the next event touches them.

**Non-Goals:**
- Changing the four-tier cascade logic itself (tier caps, batch sizes, prompt format) — that stays as-is.
- Storing events on the Lua side before the Python roundtrip — event injection is Python→Lua via `state.mutate.batch`.
- Implementing a persistent deferral queue that survives service restarts — deferred characters simply get compacted next time any event triggers their check.
- Exposing the compaction budget as an MCM (in-game) setting — it will be a Python-side config constant.

## Decisions

### 1. Witness injection as a single `state.mutate.batch` call

**Decision:** After `handle_event()` returns, build one mutation list with an `append` to `events` for every candidate character ID and send it in a single `mutate_batch()` roundtrip.

**Rationale:** The Lua handler already iterates an array of mutations and applies them sequentially. Batching all witness appends into one WS message avoids N roundtrips and keeps the mutation atomic from the Python perspective.

**Alternative considered:** Injecting events Lua-side in the trigger before sending to Python. Rejected because the trigger layer does not know which characters will be candidates (that is assembled in `talker_ws_integration`) and because Python needs to decide what event text to store (e.g., post-template rendering).

### 2. Exclude dead/despawned candidates from injection

**Decision:** Before injecting, filter candidates to only those with `is_alive: true` in their candidate dict. Dead NPCs (e.g., `victim` in a DEATH event) should not receive new events.

**Rationale:** The `candidates` list can include the victim character. Injecting an event into a dead NPC's memory wastes storage and could produce nonsensical compaction output.

### 3. Budget-pool as an `asyncio.Semaphore` with priority queue

**Decision:** Create a new `CompactionScheduler` class in `memory/scheduler.py`. After witness injection, it:
1. Queries `npc.memories.tiers` for all touched+witness character IDs in one batch query.
2. Scores each character by how much their tiers exceed the caps (sum of `max(0, count - cap)` across all tiers).
3. Sorts by score descending.
4. Runs `check_and_compact()` for the top N characters (where N = budget, default 3).
5. The rest are logged as deferred.

**Rationale:** The score reflects compaction urgency. Using `Semaphore(budget)` limits concurrent LLM calls. The scheduler itself runs as a single `asyncio.Task`, serially awaiting each character's compaction within the budget, so the `_active_compactions` guard in `CompactionEngine` still prevents overlaps.

**Alternative considered:** A global background queue that accumulates characters and drains periodically. Rejected as over-engineered for the current scale (typically 2-8 candidates per event).

### 4. Budget is a module-level constant, not MCM-synced

**Decision:** `COMPACTION_BUDGET = 3` in `memory/scheduler.py`.

**Rationale:** This is a performance knob, not a gameplay preference. Keeping it Python-side avoids config-sync complexity. It can be promoted to `config.py` later if needed.

### 5. Event text for witness injection

**Decision:** Use a short templated string like `"Witnessed: {event_type} — {actor_name} {verb} {victim_name}"` built from the event context dict. This is a lightweight summary, not the full LLM-generated dialogue.

**Rationale:** Witnesses observe the raw event, not the spoken dialogue. Storing a compact description keeps the events tier lean. The compaction LLM can later compress these into narrative summaries.

### 6. ConversationManager post-dialogue hook refactor

**Decision:** Replace the `_characters_touched` loop with two sequential steps:
1. `_inject_witness_events(event, candidates)` — mutate_batch append for all alive candidates.
2. `_schedule_compaction(candidates)` — call `CompactionScheduler.schedule(character_ids)`.

Both are called after `handle_event()` returns the speaker/dialogue pair.

**Rationale:** Clean separation of concerns. The old `_characters_touched` set is no longer needed — all candidates are witnesses by definition.

## Risks / Trade-offs

- **[Risk] Large candidate lists → big mutation batch** → Mitigation: In practice, Lua caps candidates to nearby NPCs (typically ≤10). The mutation handler iterates linearly. If this ever becomes a problem, we can add a cap on witness injection count.
- **[Risk] Scoring requires an extra `npc.memories.tiers` batch query** → Mitigation: One WS roundtrip for N characters is cheap (~5ms). The alternative (compact all, no scoring) would waste LLM calls on characters below cap.
- **[Risk] Deferred characters may accumulate many events before being compacted** → Mitigation: The tier caps are generous (events=100). A character would need to witness 100+ events without being compacted to hit the cap. The next time they're in any candidate list, they'll be top-priority in the scorer.
- **[Trade-off] `_characters_touched` set removed** → Characters explicitly queried by the LLM no longer get preferential compaction. The priority scorer handles this instead — queried characters tend to have more events and thus higher scores anyway.
