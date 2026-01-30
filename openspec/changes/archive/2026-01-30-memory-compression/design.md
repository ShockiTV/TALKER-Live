## Context

NPCs witness events during gameplay which are stored in the event_store. Before compression, all witnessed events were passed directly to dialogue prompts, causing context overflow as events accumulated. The Lua game client stores events and manages memory, while the Python service handles LLM calls for dialogue generation.

The system must work within these constraints:
- LLM context windows are limited (~4K-8K tokens for dialogue)
- Events accumulate indefinitely during gameplay
- Memory must persist across save/load cycles
- Compression is computationally expensive (requires LLM call)
- Game should not block during compression

## Goals / Non-Goals

**Goals:**
- Prevent context overflow while maintaining narrative continuity
- Provide recent event detail for immediate dialogue context
- Summarize older events into coherent long-term memory
- Handle temporal gaps in gameplay (sleep, travel)
- Migrate existing saves to new format without data loss

**Non-Goals:**
- Real-time memory streaming (batch compression is sufficient)
- Per-event compression (too expensive, batch is more efficient)
- Shared memories between characters (each NPC has independent memory)
- Memory forgetting/decay (out of scope for this change)

## Decisions

### Decision 1: Three-Tier Architecture

**Choice:** Recent events (raw) → Mid-term (900 char summary) → Long-term (6400 char narrative)

**Rationale:** Single-tier would either lose detail (all summarized) or overflow (all raw). Two tiers don't handle the accumulation problem well. Three tiers provide:
- Tier 1: Full detail for last ~12 events (immediate context)
- Tier 2: Summary when events are compressed (mid-term reference)
- Tier 3: Incrementally updated narrative (long-term continuity)

**Alternatives considered:**
- Rolling window (drop oldest events) - loses important memories
- Single summary - loses recent detail needed for dialogue
- Vector database - overcomplicated for this use case

### Decision 2: Threshold-Based Compression Trigger

**Choice:** Trigger compression when new_events >= 12

**Rationale:** 
- 12 events provides enough context for dialogue without overflow
- Batching is more efficient than per-event compression
- Background execution prevents blocking dialogue generation

**Alternatives considered:**
- Time-based (every N minutes) - wasteful when inactive, delayed when active
- Token-count based - more accurate but complex to implement
- Manual trigger - poor UX

### Decision 3: Compression in Python Service

**Choice:** Python service handles all LLM calls for compression

**Rationale:**
- Async Python is better suited for HTTP/LLM calls than Lua
- Centralized prompt management in Python
- Non-blocking via background tasks
- Reuses existing LLM client infrastructure

**Alternatives considered:**
- Lua-side compression - would block game, HTTP handling is poor
- Separate compression service - unnecessary complexity

### Decision 4: Time Gap Events (type="GAP")

**Choice:** Inject synthetic GAP events when time between events exceeds threshold

**Rationale:**
- Helps LLM understand temporal transitions
- "12 hours passed" is more useful than raw timestamp math
- Identified by type, no special flags needed

**Alternatives considered:**
- Timestamp annotations - LLMs struggle with raw timestamps
- No gap handling - confusing narratives when time jumps

### Decision 5: Per-Character Locks

**Choice:** asyncio.Lock per character_id prevents concurrent compression

**Rationale:**
- Multiple dialogue events could trigger compression for same character
- Without locks, race conditions corrupt memory state
- Lock check is non-blocking (skip if already compressing)

## Risks / Trade-offs

**[Risk] LLM generates poor summary** → Mitigated by detailed prompts with constraints (third person, chronological, factual). Low temperature (0.3) reduces creativity.

**[Risk] Compression fails mid-process** → Memory state unchanged until successful update. Retried automatically on next dialogue generation.

**[Risk] Save format migration fails** → Migration logic handles both old (array) and new (narrative) formats. Threshold exceeded → marks for immediate compression rather than data loss.

**[Trade-off] 12 event threshold is arbitrary** → Could be made configurable in future. Current value balances context vs. compression frequency.

**[Trade-off] 6400 char limit may truncate long narratives** → Prompt instructs aggressive compression. Could increase limit if models support larger context.
