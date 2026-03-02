## Context

The current TALKER dialogue system uses a 2-call LLM pattern per event: one call to select a speaker from witnesses, then a second to generate dialogue with that speaker's memory context. NPC memory is a single flat narrative blob per character (max 6400 chars) plus a global event store (12-event compression threshold). This architecture doubles API cost, introduces unnecessary latency, and loses structured event detail through premature summarization. The global event store means all NPCs share the same event list regardless of who witnessed what.

The target architecture is defined in `docs/Tools_Based_Memory.md` — a comprehensive design document covering all subsystems. This change implements the core subsystems (D+E+F+H) as a walking skeleton, deferring peripheral subsystems (A: dynamic faction relations, B: notable NPCs in system prompt, C: gender fixes, G: unique NPC background seeding) to future changes.

## Goals / Non-Goals

**Goals:**
- Halve LLM calls per event from 2 to 1 via tool-calling conversation turn
- Store 500+ events of structured NPC history in ~72 KB per character via four-tier compaction
- Per-NPC event fan-out in Lua (witnesses only see events they were near)
- Eliminate flag-based dialogue gating; consolidate trigger logic into enable/chance controls
- Provide structured Background per NPC (traits, backstory, connections) generated on first speak
- Make memory storage resilient to Python service disconnects (Lua owns all writes)

**Non-Goals:**
- Dynamic faction relations matrix in event messages (deferred — subsystem A)
- Notable Zone inhabitants in system prompt (deferred — subsystem B)
- Gender field fixes and voice consistency audit (deferred — subsystem C)
- Unique NPC background seeding from pre-generated Lua data (deferred — subsystem G)
- Provider-specific optimization layers (prompt caching, tool result cleanup)
- Conversation witnesses / chain tracking across multi-turn dialogue chains
- Budget-pool batch trigger for compaction (simplified to per-NPC threshold initially)
- `get_character_info` tool and squad discovery path (deferred to background generation change)
- Timestamp-based diff reads (deferred — optimization, not required for v1)

## Decisions

### 1. Walking skeleton build order

**Decision**: Build DEATH event end-to-end first (Lua memory store → trigger → WS → Python ConversationManager → tool calls → display), then widen to all event types and remaining tiers.

**Rationale**: De-risks the cross-language integration early. A single event type exercises every layer boundary. If DEATH works, widening is mechanical.

**Alternative considered**: Layer-complete approach (build all of Lua first, then all of Python). Rejected because integration bugs surface late, and no working dialogue until both sides complete.

### 2. Lua owns all memory writes

**Decision**: Event fan-out to witness memory stores happens entirely in Lua (direct function calls, no WS roundtrip). Python writes back compaction results and backgrounds via `state.mutate.batch`.

**Rationale**: Events are never lost due to service disconnects. Lua's memory store is authoritative. Python is a consumer/optimizer of that data. This matches the existing pattern where Lua owns game state.

**Alternative considered**: Python-side memory store. Rejected because WS disconnect = lost events, and adds another persistence layer.

### 3. Single LLM call with tools replaces 2-call pattern

**Decision**: Replace `SpeakerSelector` LLM call + `DialogueGenerator` LLM call with a single `ConversationManager` turn. The LLM receives event + candidate traits in one message and uses tools (`get_memories`, `background`) to read memory before generating dialogue.

**Rationale**: Halves LLM cost. Speaker selection becomes contextual — the LLM sees memories before committing to a speaker. One fewer WS roundtrip for the state query batch.

**Tradeoff**: The LLM may call `get_memories` for a speaker it doesn't end up using. In practice the candidate list is 2-5 NPCs and the LLM commits to its initial pick.

### 4. state.mutate.batch as symmetric write protocol

**Decision**: Add `state.mutate.batch` WS topic that mirrors `state.query.batch`. Four verbs: `append`, `delete`, `set`, `update`. Deletes use explicit IDs to eliminate race conditions.

**Rationale**: The existing batch query pattern works well — same envelope format, same error isolation. ID-based deletes mean Lua events added between Python's read and write are never accidentally deleted.

**Alternative considered**: Individual mutation commands (like current `memory.update`). Rejected because compaction requires atomic multi-resource operations (delete events + append summaries in one batch).

### 5. Flags elimination

**Decision**: Remove the `flags` dict from events entirely. Replace with two trigger controls: `enable` (bool) and `chance` (0-100). `is_important` is a local variable in trigger scripts, never sent on the wire.

**Rationale**: The current flag system is ad-hoc — different flags are read by different layers (Lua, Python) with no clear contract. The new design moves all gating to the trigger layer. Python receives only events that should generate dialogue.

### 6. Compaction uses separate fast model

**Decision**: Compaction LLM calls use the `model_name_fast` config (already exists for speaker selection). Initially, compaction runs per-NPC when the events tier exceeds its cap (100), not using budget-pool batching.

**Rationale**: Compaction is summarization — doesn't need the expensive dialogue model. Per-NPC threshold is simpler to implement and debug. Budget-pool can be added later if performance requires batching.

### 7. Save migration from v2 to v3

**Decision**: When loading a v2 save (flat narrative blob), convert the existing narrative to a single core-tier entry. Events tier starts empty. This preserves the NPC's accumulated history in a degraded but functional form.

**Rationale**: Losing all memory on upgrade is bad UX. A narrative blob maps cleanly to a single core entry — it's already compressed text. New events accumulate normally from there.

## Risks / Trade-offs

- **[Large breaking change]** → No backward compatibility period. Old saves get one-way migration. All tests need rewrite. Mitigation: skeleton-first approach catches integration issues early, tests written at end.
- **[Tool-calling LLM required]** → Some providers/models don't support tool calling well. Mitigation: the existing model recommendations already favor tool-capable models. Fallback: could add a no-tools path later that uses structured prompts.
- **[72 KB per NPC at full capacity]** → With 300+ NPCs, saves grow by 5-6 MB. Mitigation: analysis in design doc shows this is 8-10% of typical Anomaly saves. Most NPCs won't reach full capacity.
- **[Compaction quality depends on fast model]** → Cheap models may produce lower-quality summaries. Mitigation: compaction is narrative summarization, the easiest LLM task. Even small models handle it well.
- **[Race condition window]** → Between Python reading events and sending delete+append mutation, new Lua events may arrive. Mitigation: ID-based deletes by design — new events have different IDs and are untouched.
