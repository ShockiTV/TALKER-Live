# Memory Rework Design — Embedding-Based Chunked Memory

> **Status**: Exploration / Early Design  
> **Started**: 2026-02-23  
> **Last Updated**: 2026-02-23

This document captures design thinking for replacing the current single-blob narrative memory system with a chunked, embedding-indexed architecture. Discussion is ongoing — open questions remain at the bottom.

---

## Motivation

### Problems with Current System

1. **Single blob destroys history** — Each NPC has one narrative string (max 6400 chars). Every compression cycle overwrites it, progressively losing older memories. An NPC who witnessed 200 events retains roughly the same detail as one who witnessed 20.

2. **Compression only triggers during dialogue** — `_maybe_compress_memory` runs inside `generate_dialogue()`. NPCs who are never spoken to accumulate unbounded raw events that are never compressed.

3. **Fixed 12-event threshold is arbitrary** — `COMPRESSION_THRESHOLD = 12` has no relationship to text quality, embedding effectiveness, or LLM context windows. It was a convenient number, not an optimized one.

4. **No relevance filtering** — The entire narrative blob is injected into every prompt regardless of conversational context. If you ask an NPC about a recent firefight, they also "remember" unrelated events from days ago with equal weight.

5. **Per-NPC summaries required** — Different NPCs witness different events. A global summary would be wrong — each NPC needs their own memory chain because their witness lists differ.

---

## Proposed Architecture

### Core Idea

Replace the single narrative blob per NPC with **multiple memory chunks**, each paired with an **embedding vector** for relevance-based retrieval at prompt time.

### Two-Tier Chunk Model

| Tier | Purpose | Typical Size | Max Chunks | Lifecycle |
|------|---------|-------------|------------|-----------|
| **Mid-term** | Recent period summaries | ~700 chars | ~12–15 per NPC | Created from raw events; oldest compact into long-term |
| **Long-term** | Compressed historical summaries | ~1000 chars | ~6–10 per NPC | Created by merging 3 mid-term chunks; oldest re-compacted or evicted |

### Chunk Schema (Saved in Lua)

```
MemoryChunk {
    text: string          -- The summary content (700-1000 chars)
    time_start_ms: number -- Earliest event timestamp covered
    time_end_ms: number   -- Latest event timestamp covered  
    tier: string          -- "mid" or "long"
}
```

Embeddings are computed **on-the-fly** in Python at retrieval time — NOT stored in saves. This keeps chunks lightweight (~1 KB each) and decouples the embedding model from the save format.

### Per-Character Memory Structure (in saves)

```lua
-- Current:
narrative_memories[char_id] = {
    narrative = "...",           -- single blob, max 6400 chars
    last_update_time_ms = 12345
}

-- Proposed:
character_memories[char_id] = {
    raw_events = { event, event, ... },  -- temporary buffer, pruned after compression
    mid_term = { chunk, chunk, ... },    -- ordered by time
    long_term = { chunk, chunk, ... },   -- ordered by time
}
```

### Event Store Decommissioned

The global `event_store` is **eliminated entirely**. In the current system, every event is stored in a global ledger keyed by `game_time_ms` and never pruned — growing unbounded in saves.

In the new system:
- **ZMQ events are fire-and-forget messages.** Lua publishes them, Python receives them, done. No storage on the Lua side for the event-as-message.
- **Per-witness `raw_events`** in `memory_store` are the NPC's actual memory of what they perceived. These are persisted in saves and represent the only event storage in the system.
- The two concerns are unrelated — events flow through the system as messages, while raw_events are a separate per-NPC memory buffer.

### Junk Events: Store Only on Reaction

Junk event types (`ARTIFACT`, `ANOMALY`, `RELOAD`, `WEAPON_JAM`) are **conditionally stored** — only when they produce a reaction.

The reaction check happens entirely in **Lua** (cooldown, proximity, importance — the same gates triggers already have):

| Outcome | Store in raw_events | Publish to Python |
|---------|---------------------|-------------------|
| Junk + **reaction** | Yes, for all witnesses | Yes — chain continues normally |
| Junk + **no reaction** | No | No — event discarded entirely |

For comparison, non-junk events (DEATH, INJURY, etc.) are **always** stored in witnesses' raw_events and published, regardless of reaction.

**Why**: If an NPC reacts to finding an artifact, witnesses should remember seeing the find — not just a disconnected dialogue about artifacts. The event's memory value is conditional on whether anyone cared enough to react.

In the current system, junk events count toward the 12-event compression threshold despite contributing zero text to narratives. This is eliminated — junk events that don't produce reactions never enter the memory pipeline at all, and those that do carry proper context.

---

## Embedding Model Analysis

### Recommendation: `all-MiniLM-L6-v2` (384d, on-the-fly)

| Model | Dimensions | Context | Disk | RAM | Speed (CPU) |
|-------|-----------|---------|------|-----|-------------|
| **all-MiniLM-L6-v2** | **384** | **512 tokens** | **~90 MB** | **~90 MB** | **~5-10ms/chunk** |
| nomic-embed-text | 768 | 8K tokens | ~270 MB | ~300 MB | ~10-20ms/chunk |
| text-embedding-3-small | 1536 | 8K tokens | API only | N/A | network-bound |

### Key Decision: On-the-fly Embeddings, No Storage

**Embeddings are NOT stored in saves.** They are computed on-the-fly in Python whenever retrieval is needed. This means:

- **No embedding vectors in saves** — chunks store only text + metadata
- **2x more text per save budget** compared to storing 768d f16 b64 vectors
- **No migration concern** — if the embedding model changes, nothing in saves needs updating
- **Lua never touches embeddings** — purely a Python service concern
- **Upgrading the model later is free** — just swap the Python dependency

**Why 384d is right for on-the-fly**: With no storage cost, the model choice is purely about RAM and speed. 384d at ~90 MB RAM and ~5-10ms per chunk is negligible. Embedding an entire NPC's memory store (15-25 chunks) takes ~100-200ms — noise compared to a 2-10 second LLM call.

**Why not 768d**: When embeddings aren't stored, the only advantage of 768d is marginally better retrieval quality. But our chunks are small (700-1000 chars) — right in 384d's sweet spot. The 200 MB RAM savings matters more.

### Runtime Profile

Local user runs: Anomaly game + Python service + embedding model (~90 MB) + (optional) mic service.  
LLM for prompts is always remote (Gemini, OpenRouter, etc.).

---

## Chunk Size Optimization

### Principle: Size Driven by Embedding Quality, Not Event Count

The old system triggered compression at 12 events regardless of text volume. The new system should trigger based on **accumulated raw text size**, targeting chunk outputs in the embedding model's quality sweet spot.

### Embedding Quality Sweet Spots by Dimension

Training data for modern embedding models (MS MARCO passages, Natural Questions, Wikipedia paragraphs) clusters around specific text lengths. Quality curves show:

| Dimension | Sweet Spot (chars) | Peak Quality Range |
|-----------|-------------------|-------------------|
| **384d** | **400–1200** | **Degrades noticeably beyond 1500** |
| 768d | 800–2400 | Gradual falloff beyond 3000 |
| 1536d | 1000–4000 | Tolerant of longer text |

### Derived Trigger and Target Sizes

With 384d on-the-fly embeddings, defaults sit comfortably inside the sweet spot with headroom:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Compression trigger** | ~1600 chars accumulated raw text | Produces summaries of ~700 chars at ~50% compression |
| **Mid-term chunk target** | ~700 chars | Center of 384d sweet spot (400–1200), well away from edges |
| **Long-term chunk target** | ~1000 chars | Upper-center of sweet spot, ~200 chars headroom before quality degrades |
| **Events per trigger** | ~10–20 (variable) | Derived from ~80–150 chars per event description |

### Why Variable, Not Fixed Count

Event descriptions vary widely:
- Death events: ~100–150 chars ("Loner 'Wolf' was killed by a pack of blind dogs near the Army Warehouses")
- Idle/reload events: ~50–80 chars ("Reloaded weapon near campfire")
- Artifact events: ~120–180 chars (includes artifact name, anomaly field, location)

A fixed count of 12 might produce 600 chars (all short events) or 2000 chars (all detailed events). Text-size triggering normalizes this.

---

## Storage Budget Analysis

### Per-Chunk Cost (No Stored Embeddings)

| Component | Size | Notes |
|-----------|------|-------|
| Text | ~0.7–1 KB | 700–1000 chars |
| Metadata | ~50 bytes | timestamps, tier label |
| **Total per chunk** | **~1 KB** | |

### Per-NPC and Total Budget

With smaller chunks, no embeddings, and generous caps (100 raw + 35 mid + 25 long):

| Scenario | Chunks/NPC | Per NPC | 30 NPCs | 50 NPCs | 100 NPCs |
|----------|-----------|---------|---------|---------|----------|
| Light play (5-10 hrs) | 5–10 | 5–10 KB | 150–300 KB | 250–500 KB | 500 KB–1 MB |
| Medium play (20-40 hrs) | 15–30 | 15–30 KB | 450–900 KB | 750 KB–1.5 MB | 1.5–3 MB |
| Heavy play (100+ hrs) | 50–60 | 50–70 KB | 1.5–2.1 MB | 2.5–3.5 MB | 5–7 MB |

### Context: STALKER Anomaly Save Files

- Vanilla Anomaly saves: ~5–20 MB
- GAMMA modpack saves: ~15–40 MB (more mods serializing data)
- TALKER's current save footprint: ~50–200 KB (events + single narrative blobs)

Even the worst case (100 NPCs, heavy play) adds ~7 MB — roughly 20% of a GAMMA save. Typical sessions (30 NPCs, medium play) add ~1 MB. Well within budget.

### Load/Save Latency

Anomaly serializes Lua tables in a single frame. 1-4 MB of string/table data is comparable to what other GAMMA mods already serialize (Dynamic News, Trader Overhaul). No hitch expected.

---

## Event Chain Tracking & `conversation_witnesses`

### Problem: Witness Drift

Events form chains: a DEATH triggers dialogue, which might trigger a follow-up reaction. Between chain steps, NPCs move — witnesses at chain start may not be present at chain end, and new NPCs may arrive. The question "who needs a compression check?" can't be answered by looking at the last event's witnesses alone.

### Solution: `conversation_witnesses` Field

A **set of NPC IDs** that accumulates across the entire event chain. It flows through every message in the chain:

```
Lua → Python:  game.event { witnesses: [...], conversation_witnesses: [...] }
Python → Lua:  dialogue.display { ..., conversation_witnesses: [union so far] }
Lua → Python:  game.event (DIALOGUE) { witnesses: [proximity], conversation_witnesses: [bigger union] }
Python:         (no reaction) → chain ends → compression check for all IDs
```

| Field | Meaning | Used for |
|-------|---------|----------|
| `witnesses` | Who is **currently here** and perceives this specific event | Storing raw_events per-witness |
| `conversation_witnesses` | Union of **everyone involved** across the whole chain | Compression check when chain ends |

**Rules:**
- Every Python→Lua command that can trigger a follow-up event carries `conversation_witnesses`
- Every Lua event that results from such a command unions the new proximity witnesses into `conversation_witnesses` and sends it back
- Only NPC IDs are stored in the set — lightweight
- Python never drops the field — it passes through and grows

### Chain Termination

A chain ends when Python decides not to send another event-producing command:
- **No speaker selected** — no one reacts to the event
- **Junk event** — triggers dialogue check but junk events don't chain
- **`is_silent` dialogue** — NPC reacts internally but doesn't speak (future)
- **Python decides no follow-up** — dialogue generated, no further reaction

At chain end, Python iterates `conversation_witnesses` and checks each NPC's `raw_events` buffer size for compression need.

### Dialogue Event Witnesses

**Current bug**: `_create_dialogue_event` hardcodes witnesses to `[speaker, player]` — bystanders who heard the original event lose track of the conversation.

**New behavior**: The dialogue event goes through `event_near_player` which recalculates proximity witnesses. Everyone currently nearby who hears the dialogue gets it as a raw_event. The original witnesses who walked away do NOT get the dialogue event — they didn't hear it.

The `conversation_witnesses` field ensures those departed witnesses still get checked for compression, even though they missed the dialogue.

---

## Compression & Compaction Lifecycle

### Flow

```
Per-NPC raw_events (in memory_store)
    │
    │  accumulate until sum(describe(raw_events)) ≥ ~3000-4000 chars
    │  (checked at chain end via conversation_witnesses)
    │
    ▼
[LLM Summarize] → Mid-term Chunk (~700 chars)
    │              raw_events pruned after successful compression
    │
    │  when mid-term count exceeds cap (default 35)
    │
    ▼
[LLM Merge 3 oldest mid-term] → Long-term Chunk (~1000 chars)
    │
    │  when long-term count exceeds cap (default 25)  
    │
    ▼
[LLM Re-compact 2 oldest long-term] → 1 Long-term Chunk (~1000 chars)
    │  (oldest chunk evicted)
```

### Bounding Guarantees

- Raw events pruned after compression — buffer stays small
- Mid-term capped at N chunks → oldest always compact into long-term
- Long-term capped at M chunks → oldest re-compact, preventing unbounded growth
- Total memory per NPC bounded at: `raw_events buffer + (N × ~700) + (M × ~1000)` chars — deterministic ceiling

### When Compression Runs

**Current problem**: Compression only triggers during `generate_dialogue()`. NPCs who are never spoken to accumulate unbounded raw events.

**New behavior**: Compression checks trigger at **chain end** — when Python decides not to produce a follow-up event. Python iterates `conversation_witnesses`, queries each NPC's raw_event buffer size, and compresses any that exceed the text-size threshold.

This means compression runs whenever events happen near the player, not only during dialogue generation. Every event chain eventually terminates, and every witness gets checked.

---

## Retrieval at Prompt Time

### Two-Tier Scoring Model

Memory data splits into two types with different scoring strategies. All coefficients are MCM-configurable.

#### Tier 1: Memory Chunks (text, embedded) — Semantic + Recency

Chunks are prose summaries. Their content matters most, with a recency bias:

```python
semantic_w = config.retrieval_semantic_weight   # MCM, default 0.7
score = semantic_w * cosine_sim(query_vec, chunk_vec) + (1 - semantic_w) * recency_decay(chunk)
```

- `cosine_sim`: On-the-fly embedding similarity (384d, all-MiniLM-L6-v2). Typical range: 0.2–0.8 for meaningful matches.
- `recency_decay`: Inverse decay — `1 / (1 + hours_since / half_life)` where `half_life` is configurable (MCM `memory_recency_half_life`, default 12 game-hours)
- Chunk scores range roughly **0.17–0.86** in practice.

The 0.7/0.3 split ensures semantically relevant old memories can still surface (e.g., a firefight memory from 3 days ago breaking through when another firefight happens).

#### Tier 2: Raw Events (structured, no embeddings) — Programmatic Scoring

Raw events are small structured objects. Field matching is instant and deterministic:

```python
type_w     = config.retrieval_raw_type_weight      # MCM, default 0.4
location_w = config.retrieval_raw_location_weight   # MCM, default 0.2
recency_w  = config.retrieval_raw_recency_weight    # MCM, default 0.4
tier_w     = config.retrieval_raw_tier_weight       # MCM, default 0.65

raw_base = 0.0
if evt["type"] == current_event["type"]:
    raw_base += type_w
if evt["location"] == current_event["location"]:
    raw_base += location_w
raw_base += recency_score(evt["timestamp"]) * recency_w

score = raw_base * tier_w   # scale into chunk-comparable range
```

No embeddings needed — raw events are too short (~80-150 chars) for good embedding quality anyway. The type + location + recency axes capture the relevant dimensions directly.

#### Inter-Tier Balance: Why `tier_weight` Matters

Without scaling, raw events with binary type+location match score up to **1.0**, while the best chunks top out around **0.86**. This means raw events with matching type+location *always* beat chunks, even when embedding similarity confirms the chunk is more relevant.

The `retrieval_raw_tier_weight` (default **0.65**) compresses raw scores into the 0–0.65 range so they compete fairly with chunks. Worked examples with `half_life=12h`:

**DEATH trigger at Garbage:**

| Item | Breakdown | Score |
|------|-----------|-------|
| Chunk: high sim recent (sim=0.8, 2h) | 0.7×0.8 + 0.3×0.857 | **0.82** |
| Raw: DEATH at Garbage, 5m ago | (0.4+0.2+0.4×1.0) × 0.65 | **0.65** |
| Chunk: death memory (sim=0.6, 48h) | 0.7×0.6 + 0.3×0.2 | **0.48** |
| Raw: DEATH at Cordon, 2h ago | (0.4+0+0.4×0.857) × 0.65 | **0.48** |
| Raw: ARTIFACT at Garbage, fresh | (0+0.2+0.4×1.0) × 0.65 | **0.39** |
| Raw: no match, fresh | (0+0+0.4×1.0) × 0.65 | **0.26** |
| Chunk: low relevance (sim=0.2, old) | 0.7×0.2 + 0.3×0.1 | **0.17** |
| Raw: no match, old | (0+0+0.4×0.1) × 0.65 | **0.03** |

Key behaviors:
- Highly relevant chunks **beat** raw events (0.82 > 0.65)
- A relevant death chunk **ties** with a less-relevant raw death (0.48 = 0.48)
- An irrelevant artifact raw event (0.39) **loses** to the death chunk (0.48)
- Irrelevant raw events fall to the bottom

**"Tell me about the emissions" (player chat, DIALOGUE trigger):**

| Item | Breakdown | Score |
|------|-----------|-------|
| Raw: DIALOGUE at Garbage, fresh | (0.4+0.2+0.4×1.0) × 0.65 | **0.65** |
| Chunk: emission story (sim=0.7, 100h) | 0.7×0.7 + 0.3×0.107 | **0.52** |
| Chunk: emission story (sim=0.8, 100h) | 0.7×0.8 + 0.3×0.107 | **0.59** |
| Raw: IDLE, no match, fresh | (0+0+0.4×1.0) × 0.65 | **0.26** |

Recent dialogue raw events still rank high (they ARE useful conversation history), but relevant emission chunks compete closely — especially with high cosine similarity. The emission memory is no longer drowned out 2:1.

#### Coefficient Defaults Summary

| Coefficient | Default | Rationale |
|-------------|---------|-----------|
| `retrieval_semantic_weight` | 0.7 | Embedding similarity dominates for chunks — the whole point of having an embedding model |
| `retrieval_raw_type_weight` | 0.4 | Same event type is relevant but shouldn't dominate (down from 0.5) |
| `retrieval_raw_location_weight` | 0.2 | Same location is a weak signal (down from 0.3) — many events happen in the same spot |
| `retrieval_raw_recency_weight` | 0.4 | Fresh raw events should rank high even without type/location match (up from 0.2) |
| `retrieval_raw_tier_weight` | 0.65 | Scales raw scores into 0–0.65 range, comparable with chunk scores (0.17–0.86) |

The raw weights (type + location + recency = 0.4 + 0.2 + 0.4 = 1.0) sum to 1.0 before tier scaling. After tier scaling, a perfect raw event scores 0.65 — below an excellent chunk (0.82) but above a mediocre one (0.38).

### Full Retrieval Algorithm

```python
STATIC_PROMPT_TOKENS = 1700  # measured overhead of static prompt sections
OUTPUT_RESERVE_TOKENS = 200  # max_tokens for LLM response
CHARS_PER_TOKEN = 3.5        # conservative for mixed English/Zone jargon

async def retrieve_memories(
    character_id: str,
    current_event: dict,
    config: ConfigMirror,           # all MCM settings
):
    char_budget     = config.memory_retrieval_characters     # default 12000
    context_tokens  = config.memory_context_tokens           # default 30000
    half_life       = config.memory_recency_half_life        # default 12
    semantic_w      = config.retrieval_semantic_weight        # default 0.7
    raw_type_w      = config.retrieval_raw_type_weight       # default 0.4
    raw_loc_w       = config.retrieval_raw_location_weight   # default 0.2
    raw_recency_w   = config.retrieval_raw_recency_weight    # default 0.4
    raw_tier_w      = config.retrieval_raw_tier_weight       # default 0.65

    query_text = describe_event(current_event)
    query_vec = embed(query_text)
    current_time_ms = current_event["game_time_ms"]
    
    # Token ceiling: how many chars of memory can fit in the model context
    available_tokens = context_tokens - STATIC_PROMPT_TOKENS - OUTPUT_RESERVE_TOKENS
    token_char_limit = int(available_tokens * CHARS_PER_TOKEN)
    
    # Effective budget is the stricter of the two constraints
    effective_budget = min(char_budget, token_char_limit)
    
    # --- Tier 1: Score memory chunks ---
    chunks = mid_term[character_id] + long_term[character_id]
    scored_chunks = []
    for chunk in chunks:
        chunk_vec = embed(chunk.text)  # on-the-fly
        sim = cosine_sim(query_vec, chunk_vec)
        hours_since = (current_time_ms - chunk.time_end_ms) / 3_600_000
        recency = 1 / (1 + hours_since / half_life)
        score = semantic_w * sim + (1 - semantic_w) * recency
        scored_chunks.append((chunk, score))
    
    # --- Tier 2: Score raw events ---
    raw_events = raw_events_store[character_id]
    scored_raw = []
    for evt in raw_events:
        raw_base = 0.0
        if evt["type"] == current_event["type"]:
            raw_base += raw_type_w
        if evt.get("location") == current_event.get("location"):
            raw_base += raw_loc_w
        hours_since = (current_time_ms - evt["game_time_ms"]) / 3_600_000
        raw_base += (1 / (1 + hours_since / half_life)) * raw_recency_w
        score = raw_base * raw_tier_w   # scale into chunk-comparable range
        scored_raw.append((evt, score))
    
    # --- Merge and fill by score until budget exhausted ---
    all_scored = (
        [(item, score, "chunk") for item, score in scored_chunks] +
        [(item, score, "raw") for item, score in scored_raw]
    )
    all_scored.sort(key=lambda x: x[1], reverse=True)
    
    selected = []           # [(item, score, kind)]
    chars_used = 0
    for item, score, kind in all_scored:
        text = item.text if kind == "chunk" else describe_event(item)
        if chars_used + len(text) <= effective_budget:
            selected.append((item, score, kind))
            chars_used += len(text)
    
    # Re-sort by time for chronological presentation in prompt
    selected.sort(key=lambda x: get_time(x[0]))
    return [(item, kind) for item, _, kind in selected]
```

Both constraints are enforced in one place:
- `memory_retrieval_characters` (default 12,000) — user-friendly knob for memory depth
- `memory_context_tokens` (default 30,000) — safety cap for small models, converted to a char ceiling

The `effective_budget = min(char_budget, token_char_limit)` means the stricter constraint always wins. On a 30K model with 12K char budget, the char budget dominates (~12K < ~98K token ceiling). On an 8K model, the token ceiling would kick in (~21K chars) — but even then 12K is already under, so the char budget still wins. The token cap only matters if a user cranks `memory_retrieval_characters` very high on a small model.

### Query Construction

The "query" for embedding similarity is:
- **Player chat**: The player's dialogue input text
- **Event trigger** (death, artifact, etc.): `describe(trigger_event)` — the same text inserted into the prompt
- **Idle/ambient**: Description of recent events near the NPC

---

## Prompt Design: What Memory Goes Where

### Speaker Pick Prompt (fast model)

Purpose: Pick WHO speaks. Lightweight, no embeddings, no memory chunks.

Inputs:
- **Trigger event** — `describe(event)` of what just happened
- **Candidates** — each witness's name, faction, rank, personality
- **Recent raw_events** — per-witness events from last N minutes, max M per witness, fetched from Lua `memory_store`

Recent events are **grouped chronologically by event** with witness annotations to deduplicate shared experiences:

```
## CANDIDATES
A: Loner, Experienced, personality: gruff and suspicious
B: Duty, Veteran, personality: disciplined and loyal
C: Freedom, Trainee, personality: carefree and reckless

## RECENT EVENTS (oldest → newest)
[4 min ago] A heard gunfire nearby
[3 min ago] C found an artifact
[2 min ago] A and B saw a bloodsucker kill a rookie
[just now] A, B, and C saw a pack of blind dogs attack a loner ← TRIGGER
```

The LLM sees the full shared timeline and who perceived what, without per-candidate redundancy. This makes the selection asymmetry-aware — the NPC who just saw a brutal kill is more likely to react to the current event.

### Dialogue Generation Prompt (heavy model)

Purpose: Generate WHAT the speaker says. Quality model — gets the full context.

Inputs:
- **Character anchor** — name, rank, faction, backstory, personality, reputation, weapon
- **Top-K memory chunks** via embedding retrieval — query is `describe(trigger_event)`, scored by cosine similarity, re-sorted chronologically
- **Raw events** from the speaker's buffer (not just the last few minutes — all uncompressed)
- **Scene context** — location, time, weather, emission/psy-storm, campfire state
- **World state** — dead leaders, faction politics, etc.
- **Faction descriptions** and relation rules

The key difference from current: instead of one monolithic narrative blob, the dialogue prompt receives **multiple independently retrieved memory chunks** — only the most relevant ones for the current situation.

### Compression Prompt (fast model)

Purpose: Compress raw_events into a mid-term chunk.

Inputs:
- **Raw events** from one NPC's buffer (the ones being compressed)
- **Target char size** from MCM setting (`memory_midterm_chunk_size`)
- Speaker name for third-person perspective

Output: single chunk text (~700 chars).

### Compaction Prompt (fast model)

Purpose: Merge N oldest mid-term chunks into one long-term chunk.

Inputs:
- **N mid-term chunk texts** (the ones being merged)
- **Target char size** from MCM setting (`memory_longterm_chunk_size`)
- Speaker name for third-person perspective

Output: single chunk text (~1000 chars).

---

## Open Questions

These need further exploration before implementation:

### 1. Compaction Batch Size
When mid-term overflows, how many chunks merge into one long-term chunk? Current thinking: **3 → 1**. But 2 → 1 wastes less information, while 4 → 1 is more aggressive compression.

### ~~2. V1 Scope — Embeddings from Day One?~~ (RESOLVED)
With on-the-fly embeddings that are never stored, there is no save format dependency. Embeddings ship from day one with no migration concern — the model can be swapped freely since nothing is persisted.

### ~~3. Embedding Model Delivery~~ (RESOLVED)
The embedding model (`all-MiniLM-L6-v2`, ~90 MB) is a Python service dependency only. `sentence-transformers` auto-downloads on first run. Lua never touches embeddings. If the user doesn't have internet on first launch, the service falls back to chronological retrieval.

### 4. Migration Path
How to migrate existing saves with single narrative blobs to the new chunked format? The current blob could become the first long-term chunk.

### ~~5. Embedding Computation Timing~~ (RESOLVED)
Embeddings computed **on-the-fly at retrieval time** in Python. Nothing stored. The embedding model is loaded once when the Python service starts and stays in memory (~90 MB).

### ~~6. What Serves as Retrieval Query for Non-Chat Triggers?~~ (RESOLVED)
Answered in the "Query Construction" section above: player chat uses the input text, event triggers use `describe(trigger_event)`, idle/ambient uses description of recent events near the NPC. The raw event scoring tier doesn't use embeddings at all — it uses programmatic type + location + recency scoring.

### ~~7. Raw Event Buffer Safety Cap~~ (RESOLVED)
Yes — `memory_raw_event_cap` MCM setting (default 100) with oldest-eviction. This is a hard Lua-side cap independent of the soft compression trigger (~1600 chars of describe() text). Only matters if Python service is down for extended periods.

---

## MCM Settings for Memory System

All memory tuning variables should be exposed in the MCM (Mod Configuration Menu) under a new **Memory** section, allowing users to adjust the system without code changes.

### Proposed Settings

| MCM Key | Type | Default | Min | Max | Step | Description |
|---------|------|---------|-----|-----|------|-------------|
| `memory_raw_event_cap` | input | 100 | 10 | 200 | — | Max raw events per NPC before oldest-eviction (safety cap when Python unreachable) |
| `memory_compression_threshold` | input | 1600 | 500 | 4000 | — | Sum of `describe()` chars in raw_events before compression triggers |
| `memory_midterm_chunk_size` | input | 700 | 300 | 1200 | — | Target char length for mid-term summary chunks |
| `memory_longterm_chunk_size` | input | 1000 | 500 | 1500 | — | Target char length for long-term summary chunks |
| `memory_midterm_max_chunks` | track | 35 | 5 | 60 | 1 | Max mid-term chunks per NPC before compaction into long-term |
| `memory_longterm_max_chunks` | track | 25 | 3 | 40 | 1 | Max long-term chunks per NPC before re-compaction |
| `memory_compaction_batch` | track | 3 | 2 | 5 | 1 | Number of oldest mid-term chunks merged into one long-term chunk |
| `speaker_pick_time_window` | input | 300 | 60 | 600 | — | Time window in seconds for recent raw_events included in speaker pick prompt |
| `speaker_pick_max_events` | track | 5 | 1 | 10 | 1 | Max raw_events per witness included in speaker pick prompt |
| `memory_recency_half_life` | track | 12 | 2 | 48 | 1 | Game-hours for recency score to halve (inverse decay) |
| `memory_context_tokens` | input | 30000 | 4000 | 128000 | — | Model context window in tokens (safety cap — look up your model) |
| `memory_retrieval_characters` | input | 12000 | 2000 | 60000 | — | Character budget for retrieved memories in dialogue prompt |
| `retrieval_semantic_weight` | track | 0.7 | 0.1 | 0.9 | 0.1 | How much embedding similarity matters vs recency for memory chunks |
| `retrieval_raw_type_weight` | track | 0.4 | 0.0 | 0.8 | 0.1 | Weight of event-type match in raw event scoring |
| `retrieval_raw_location_weight` | track | 0.2 | 0.0 | 0.8 | 0.1 | Weight of location match in raw event scoring |
| `retrieval_raw_recency_weight` | track | 0.4 | 0.0 | 0.8 | 0.1 | Weight of recency in raw event scoring |
| `retrieval_raw_tier_weight` | track | 0.65 | 0.1 | 1.0 | 0.05 | Global scale factor — how raw event scores compete with chunk scores |

### Notes

- **Char sizes, not token counts**: Users think in text length, not tokens. The LLM prompt builder converts to tokens internally.
- **`memory_raw_event_cap`**: Hard safety cap (100) with headroom above the soft compression trigger (~75 events worth of describe() text hits 1600 chars). Only matters if Python service is down for extended periods.
- **`memory_compression_threshold`**: Higher = fewer, larger summaries, fewer LLM calls. Lower = more frequent, smaller summaries, more calls. The default (1600) produces ~700 char summaries at ~50% compression — centered in the 384d sweet spot.
- **Chunk size targets are advisory**: The LLM prompt asks for "approximately N characters" — actual output may vary. The system should not reject chunks that are slightly over/under target.
- **These values feed into Python prompts**: Lua stores them as MCM values, they get synced to Python via `config.sync` / `config.update`, and Python uses them when building compression/compaction prompts.
- **`memory_context_tokens`** (default 30000): Safety net for the total prompt size. The default of 30K fits all recommended free models (Kimi K2 128K, Qwen3 128K, DeepSeek 128K, Mistral Small 32K). Only Gemma 3 27B (8K, listed as a backup) would need a lower value. Users on 128K models can leave this alone — `memory_retrieval_characters` is the real limiter.
- **`memory_retrieval_characters`** (default 12000): Controls how much memory content `retrieve_memories` selects. At 12,000 chars (~3,400 tokens), this fits ~15-17 chunks of mixed mid/long-term memory. This is the primary knob for memory depth vs prompt quality. Higher = more context but slower and more diluted; lower = tighter, more focused recall. Even at the default, 12K chars is well under the 30K token context limit, leaving ~85% of the context for static prompt sections and headroom.
- **Retrieval scoring coefficients**: These control the inter-tier balance between memory chunks and raw events. The defaults are tuned so that: (1) highly relevant chunks beat raw events, (2) a perfect-match fresh raw event (~0.65) is competitive but doesn't dominate, (3) irrelevant raw events fall below relevant chunks. See the "Inter-Tier Balance" section for worked examples. Most users should leave these at defaults.
  - **`retrieval_semantic_weight`** (0.7): Higher = embedding similarity matters more than recency for chunks. Lower = recent chunks always win.
  - **`retrieval_raw_tier_weight`** (0.65): The most impactful scoring knob. Lower = chunks strongly favored. Higher (toward 1.0) = raw events dominate. At 0.65, a perfect raw event scores just below an excellent chunk.
  - **Raw internal weights** (type=0.4, location=0.2, recency=0.4): Summing to 1.0, these control which raw event attributes matter most. Recency at 0.4 (up from original 0.2) ensures fresh events rank high even without type/location match, and stale type matches don't inappropriately dominate.

### Config Sync

These settings follow the existing pattern:
1. Defaults in `config_defaults.lua`
2. Getters in `interface/config.lua` via `cfg()`
3. Included in `c.get_all_config()` for sync to Python
4. Mirrored in Python's `ConfigMirror` / `models/config.py`

---

## Related Documents

- [Memory_Compression.md](Memory_Compression.md) — Current system documentation
- [multi_store_memory_architecture.md](multi_store_memory_architecture.md) — Earlier proposal (reaction_store, not implemented)
