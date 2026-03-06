## Context

The current `ConversationManager` builds LLM prompts by inlining event descriptions and character backgrounds into user messages. Each dialogue turn embeds the speaker's full memory dump (events + summaries + digests + cores + background) in the user message, and the picker step inlines all candidate backgrounds as JSON. When multiple characters witness the same events, those events appear duplicated across memory dumps — 5 witnesses × 10 events = 50 event descriptions. Backgrounds are sent inline in the picker and again implicitly through memory context.

The `memory_store_v2` in Lua uses per-character monotonic `seq` counters for item identity. The Python side tracks injection state via `_memory_timestamps: dict[str, int]` (character_id → last injected timestamp). Background generation currently uses the main (expensive) LLM model.

## Goals / Non-Goals

**Goals:**
- Eliminate token waste from duplicated events/backgrounds/memories across turns
- Establish a global unique timestamp as the single identity key for all memory items
- Move all shared context (events, backgrounds, memories) to deduplicated system messages
- Reduce picker and dialogue user messages to lightweight pointers (event timestamp + character ID)
- Use the fast LLM model for background generation

**Non-Goals:**
- Changing the system message count/grouping strategy (accepted risk; separate future change)
- Changing the compaction cascade logic (compaction still works the same, just uses unique_ts)
- Modifying the wire protocol between Lua and Python
- Message window pruning strategy (orthogonal concern)

## Decisions

### Decision 1: Global unique timestamp via collision bumping (Option C)

Replace the per-character `seq` counter with a single global `unique_ts()` function in Lua. If `engine.get_game_time_ms()` returns a value ≤ the last assigned timestamp, bump to `last + 1`.

**Rationale**: A single field serves as both temporal ordering and identity key. Per-character seq was only needed because game_time_ms wasn't unique. Bumping collisions (rarely >1ms) is imperceptible in simulated game time. Alternative considered: separate `event_id` field (Option B) — rejected because it adds a second field for no benefit; the timestamp bump is <1ms drift in simulated time.

### Decision 2: Three content categories as system messages

All shared context is injected as `[system]` messages with tagged prefixes for parsing:

| Category | Tag Format | Dedup Key | Example |
|----------|-----------|-----------|---------|
| Background | `BG:{char_id}` | character_id | `BG:12467 — Wolf (Freedom)\nTraits: ...` |
| Memory | `MEM:{char_id}:{ts}` | (char_id, start_ts) | `MEM:12467:42000 — [SUMMARY] Wolf recalls...` |
| Event | `EVT:{ts}` | game_time_ms | `EVT:170042001 — DEATH: Bandit killed Loner_7\nWitnesses: Wolf(12467), Fanatic(34521)` |

Tags enable `rebuild_from_messages()` to re-parse surviving messages after pruning.

**Rationale**: System messages are the natural role for factual context that isn't a character's speech or an instruction. Tags make dedup reconstruction mechanical. Alternative: grouping all items into 3 large system messages rebuilt each turn — rejected as it loses fine-grained pruning control.

### Decision 3: DeduplicationTracker replaces _memory_timestamps

A new `DeduplicationTracker` class tracks three sets:
- `_injected_bg_ids: set[str]` — character IDs with backgrounds in messages
- `_injected_event_ts: set[int]` — event timestamps in messages
- `_injected_mem_ids: set[tuple[str, int]]` — (char_id, start_ts) pairs in messages

Before each turn, new items are checked against these sets. Only items not yet present are injected. After pruning, `rebuild_from_messages()` scans surviving system messages by tag prefix and reconstructs the sets.

**Rationale**: The old `_memory_timestamps` only tracked per-character last-seen time. The new design tracks individual items globally, enabling cross-character dedup (e.g., shared events). The rebuild method makes the tracker resilient to pruning without external coordination.

### Decision 4: Pointer-based picker and dialogue messages

The picker user message becomes: `"Pick speaker for EVT:{ts}. Candidates: {id1}, {id2}, ..."`

The dialogue user message becomes: `"Character {id} reacts to EVT:{ts}. Personal memories: {narrative_only}. React as {name} — just spoken words."`

Personal memories (summaries/digests/cores narrative text) are still included in the dialogue user message because they represent the character's subjective perspective. Events and backgrounds are NOT included — they're already in system messages.

**Rationale**: All factual context is already in the message array as system messages. The LLM can reference them by the tagged identifiers. This dramatically reduces per-turn token cost while maintaining full information availability.

### Decision 5: Background generation uses fast_llm_client

`BackgroundGenerator.__init__` accepts a `fast_llm_client` parameter. The conversation manager passes the fast client at construction time.

**Rationale**: Background generation is formulaic (JSON output from character metadata). It doesn't need the creative capability of the main model. The fast model is cheaper and faster. The compaction engine already uses the fast model for similar structured compression work.

### Decision 6: Event system messages persist through picker

Event system messages injected before the picker step are NOT ephemeral — they persist in the conversation history. Only the picker's user question and assistant response are removed. The event is a fact about the world that benefits all subsequent turns.

**Rationale**: Events are world facts, not picker-specific context. Keeping them avoids re-injection for the dialogue step and future turns. The ephemeral pattern only applies to the picker ask/response pair.

## Risks / Trade-offs

**[Risk] Many system messages accumulate** → Accepted risk for now. Future change may batch/group system messages to reduce count. Current design optimizes for dedup correctness and fine-grained pruning control.

**[Risk] LLM confusion from interleaved system messages** → Mitigated by consistent tag prefixes and structured formatting. The system prompt explains the format. Most production models handle interleaved system messages well.

**[Risk] Timestamp collision in rapid-fire events** → Mitigated by bumping to `last + 1`. Maximum drift is bounded by event rate (~10/sec worst case = 10ms drift per burst, invisible in game time).

**[Risk] rebuild_from_messages() parsing fragility** → Mitigated by strict tag format (`BG:`, `MEM:`, `EVT:`) at start of system message content. Simple string prefix matching.

**[Trade-off] Personal narrative memories still inline in user message** → Summaries/digests/cores are character perspective, not shared facts. They COULD be system messages too, but the LLM benefits from seeing them adjacent to the character's reaction instruction.

**[Trade-off] save/load migration for unique_ts** → Existing saves with per-character `seq` need migration. The `load_save_data` migration path already handles v2→v3; a v3→v4 migration stamps existing items with unique_ts values derived from their existing timestamps, falling back to sequential assignment for collisions.
