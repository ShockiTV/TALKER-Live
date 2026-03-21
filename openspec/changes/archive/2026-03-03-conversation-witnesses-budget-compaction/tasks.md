## 1. Witness Event Injection

- [x] 1.1 Add `build_witness_text(event)` helper in `dialogue/conversation.py` that formats `"Witnessed: {TYPE} — {actor} {verb} {victim}"` from event dict
- [x] 1.2 Add `_inject_witness_events(event, candidates)` method to `ConversationManager` — filters alive candidates, builds mutation list with one `append` to `events` per character, calls `state_client.mutate_batch()`
- [x] 1.3 Remove `_characters_touched` set and its tracking in the tool loop (lines ~174, ~697)
- [x] 1.4 Replace post-dialogue `_characters_touched` block (lines ~736-744) with calls to `_inject_witness_events()` and `CompactionScheduler.schedule()`
- [x] 1.5 Write unit tests for `build_witness_text()` covering DEATH, IDLE, and unknown event types

## 2. Priority Scoring

- [x] 2.1 Add `score_character(tiers: dict[str, int]) -> int` static method to `CompactionEngine` that returns `sum(max(0, count - cap) for tier)`
- [x] 2.2 Write unit tests for `score_character()` — over-cap events, multiple tiers, all-below-cap returns 0

## 3. Compaction Budget-Pool Scheduler

- [x] 3.1 Create `memory/scheduler.py` with `CompactionScheduler` class: constructor takes `CompactionEngine` + `budget: int = 3`
- [x] 3.2 Implement `schedule(character_ids: set[str])` — batch-query `npc.memories.tiers`, score each character, sort descending, run `check_and_compact()` for top N within budget, log deferred characters
- [x] 3.3 Wrap `schedule()` call site in `asyncio.create_task()` so it runs as a non-blocking background task
- [x] 3.4 Write unit tests for `CompactionScheduler` — budget limits, priority ordering, zero-score skip, batch query failure handling

## 4. ConversationManager Integration

- [x] 4.1 Add `compaction_scheduler` parameter to `ConversationManager.__init__()` (replacing raw `compaction_engine` usage for scheduling)
- [x] 4.2 Wire up `CompactionScheduler` creation in `handlers/events.py` or `__main__.py` where `ConversationManager` is constructed
- [x] 4.3 Update post-dialogue block: call `_inject_witness_events()` then `compaction_scheduler.schedule()` with all candidate IDs
- [x] 4.4 Verify `ConversationManager` still accepts `compaction_engine` for backward compat (scheduler wraps it)

## 5. Testing & Validation

- [x] 5.1 Add integration test: game event with 3 candidates → verify `mutate_batch` called with 3 append mutations (witness injection)
- [x] 5.2 Add integration test: 8 candidates with budget 3 → verify only top 3 by score get `check_and_compact()` called
- [x] 5.3 Run existing Python test suite to confirm no regressions in dialogue flow or compaction
- [x] 5.4 Update any existing tests that assert on `_characters_touched` behavior or direct `create_compaction_task()` calls
