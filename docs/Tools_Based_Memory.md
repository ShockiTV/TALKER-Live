# Tools-Based Memory Architecture

> **Status**: Exploration / Early Design  
> **Started**: 2026-02-28  
> **Last Updated**: 2026-02-28  
> **Supersedes**: [Claude_Based_Memory.md](Claude_Based_Memory.md) (Anthropic-locked `memory_tool` design)  
> **Draws From**: [Memory_Rework_Design.md](Memory_Rework_Design.md) (structured events, `conversation_witnesses`)

This document captures design thinking for a **provider-agnostic** memory architecture using standard tool calling, structured event storage, a four-tier compaction cascade, and timestamp-based diff reads. Lua owns the memory store (event fan-out, save/load). Python reads/writes via a unified store operations DSL over WebSocket. The LLM reads memories and manages character backgrounds via standard tools that work on any provider.

---

## Motivation: Why Standard Tools Instead of `memory_tool`

### The `memory_tool` Design Overfit to Anthropic

The previous design ([Claude_Based_Memory.md](Claude_Based_Memory.md)) used Anthropic's `memory_tool` to expose a virtual filesystem of per-NPC memories. But analysis of what the LLM actually needed showed:

| `memory_tool` Operation | Actually Used? | Purpose |
|------------------------|:-:|---|
| `view /memories/characters/{id}/` | Yes | Read all memory tiers |
| `create background.md` | Yes | Create character identity |
| `str_replace background.md` | Yes | Edit character traits |
| `delete` any file | No | Python handles all deletion |
| `create event_*/summary_*/etc.` | No | Python handles all writes |
| `view /global_event_backfill/` | No | Python-only bookkeeping |

The LLM's actual API surface is: **read memories, read/write background**. The virtual filesystem abstraction provided far more power than needed — and it was the thing that locked the design to Anthropic.

### Standard Tool Calling Is Universal

Every major provider supports function/tool calling with the same basic wire format:

| Provider | Tool Calling | Prompt Caching | Tool Cleanup |
|----------|:-:|:-:|:-:|
| OpenAI / GPT-4.1 | Yes | Automatic (50% off, ≥1024t prefix) | Manual (client-side truncation) |
| Anthropic / Claude | Yes | Explicit `cache_control` (90% off) | `clear_tool_uses` API |
| Google / Gemini | Yes | `cachedContent` API (32K min) | No |
| Ollama (local) | Yes (model-dependent) | Implicit KV cache | No |
| OpenRouter | Yes (pass-through) | Varies by model | Varies |
| Hosted / custom endpoint | Yes (OpenAI-compatible) | Varies | Varies |

By using standard tools, the memory architecture works on **all** of these. Provider-specific optimizations (caching, cleanup) layer on top where available.

### Structured Storage > Markdown Files

The `memory_tool` design stored everything as `.md` files because the tool spoke files. Without it, there's no reason to flatten structured events into markdown. Events arrive from Lua with structured fields (type, location, timestamp, actors) — storing them structured preserves information that prose would lose.

---

## Architecture Overview

### LLM as Game Master, Python as Memory Manager

One long-lived conversation per game session (per tenant). The LLM acts as the **game master/narrator** who voices individual NPCs. Lua handles event recording (fan-out to witnesses) and owns the memory store. Python handles memory compaction and dialogue generation via LLM calls, reading/writing the Lua store through a unified DSL.

```
┌──────────────────────────────────────────────────────────────────┐
│                         GAME (Lua)                                │
│                                                                   │
│  memory_store module (owns ALL per-NPC structured data)           │
│    <character_id> →                                               │
│      events:     [structured event, ...]   (cap: 100)            │
│      summary:    [compressed, ...]         (cap: 10)             │
│      digest:     [compressed, ...]         (cap: 5)              │
│      core:       [compressed, ...]         (cap: 5)              │
│      background: Background | nil                                 │
│    global_event_buffer: [event, ...]       (cap: 30)             │
│                                                                   │
│  Event fan-out: trigger → memory_store:append_to_witnesses()      │
│  Save/Load: marshal memory_store to/from save file                │
│  MCM: ~10 memory settings + API config                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │  WS (game.event for dialogue,
                            │  state.query.batch / state.mutate.batch)
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     PYTHON SERVICE                                │
│                                                                   │
│  SessionRegistry (existing multi-tenant infra)                    │
│    └─ per-tenant:                                                 │
│         ├─ ConfigMirror              (exists)                     │
│         ├─ SessionContext / Outbox    (exists)                     │
│         └─ ConversationManager       (NEW)                        │
│              ├─ system_prompt         (cacheable prefix)          │
│              ├─ messages[]            (growing conversation)      │
│              └─ tools: [get_memories, background,                 │
│                         get_character_info]                       │
│                                                                   │
│  Reads Lua memory via state.query.batch                           │
│    → translates technical names to human-readable                 │
│    → constructs MemoryEvent / CompressedMemory objects            │
│                                                                   │
│  Writes back via state.mutate.batch                               │
│    → compaction results (summaries, digests, cores)               │
│    → background writes (LLM-generated)                            │
└──────────────────────────────────────────────────────────────────┘
```

### Three Standard Tools

```
┌──────────────────────────────────────────────────────────────┐
│  Tool 1: get_memories (READ ONLY)                            │
│                                                              │
│  Required:  character_id: string                             │
│  Optional:  from_timestamp: number  (game-time filter)       │
│  Optional:  to_timestamp: number    (game-time filter)       │
│                                                              │
│  Returns: {                                                  │
│    character_id, as_of_timestamp,                            │
│    tiers: { core, digest, summary, events }                  │
│  }                                                           │
│                                                              │
│  Python assembles from MemoryStore, returns structured.      │
│  One call = full NPC history or timestamp-filtered diff.     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Tool 2: background (READ + WRITE)                           │
│                                                              │
│  Required:  character_id: string                             │
│  Required:  action: "read" | "write" | "update"              │
│                                                              │
│  "write":  content: { traits, backstory, connections }       │
│  "update": field + add/remove operations                     │
│  "read":   (no extra args)                                   │
│                                                              │
│  Returns: { background: Background | null }                  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Tool 3: get_character_info                                  │
│                                                              │
│  Required:  character_id: string                             │
│                                                              │
│  Returns: {                                                  │
│    character: { id, name, faction, rank, ...,                 │
│                 gender, background },                         │
│    squad_members: [{ id, name, ..., gender,                   │
│                      background }, ...]                       │
│  }                                                           │
│                                                              │
│  gender: "female" | "male". Derived from sound_prefix.        │
│          Not on the Character dataclass — only added to       │
│          this tool's response by the query handler.           │
│                                                              │
│  Side effects:                                               │
│    - Creates dirs + backfills globals for new squad members   │
│    - Returns existing backgrounds (or null)                  │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Structured Storage (Not Markdown)

Events are stored as structured objects. The human-readable `text` field is **not stored** — it is generated from templates at construction time in Python. Lua saves carry only the raw structured fields.

Lua saves store **technical identifiers** — location is `"l01_escape"`, faction is `"stalker"`, names come from the game engine (already human-readable). When Python reads events from Lua via the store DSL, it translates technical fields to human-readable at `MemoryEvent` construction time: `"l01_escape"` → `"Cordon"`, `"stalker"` → `"Loner"`. The only identifier that passes through untranslated is `character_id` — a correlation key the LLM uses to reference specific NPCs across tools.

```python
@dataclass
class CharacterRef:
    game_id: str               # correlation key (same as character_id elsewhere)
    name: str                  # "Wolf", "Petrov" (human-readable from engine)
    faction: str               # technical: "stalker", "bandit" (translated by Python)
    # optional fields carried through from game: experience, reputation, weapon, etc.

@dataclass
class MemoryEvent:
    seq: int                   # append-only, never reused
    timestamp: int             # game_time_ms (from Lua event)
    type: str                  # "DEATH", "DIALOGUE", "EMISSION", etc.
    context: dict              # per-type structured fields (see Context Schemas below)
    text: str                  # generated from template, NOT stored in Lua

@dataclass
class CompressedMemory:
    seq: int                   # append-only, never reused
    tier: str                  # "summary", "digest", "core"
    start_ts: int              # earliest event timestamp covered
    end_ts: int                # latest event timestamp covered
    text: str                  # compressed narrative (stored)
    source_count: int          # how many lower-tier items were compressed

@dataclass
class Connection:
    character_id: str          # correlation key
    name: str                  # "Fanatic" (human-readable)
    relation: str              # freeform: "mentor", "old rival", "drinking buddy"

@dataclass
class Background:
    traits: list[str]          # personality descriptors (add/remove for evolution)
    backstory: str             # narrative origin/history paragraph
    connections: list[Connection]

@dataclass
class NPCMemory:
    events: list[MemoryEvent]
    summary: list[CompressedMemory]
    digest: list[CompressedMemory]
    core: list[CompressedMemory]
    background: Background | None
```

### Context Schemas by Event Type

The `context` dict varies per event type. Character values are `CharacterRef` objects; all other values are strings/numbers.

| EventType | Context Keys | Types |
|-----------|-------------|-------|
| `DEATH` | `victim`, `killer` | Character, Character\|nil |
| `INJURY` | `actor` | Character |
| `ARTIFACT` | `actor`, `action`, `item_name` | Character, string (`"pickup"`/`"use"`/`"equip"`), string |
| `ANOMALY` | `actor`, `anomaly_type` | Character, string (technical section) |
| `EMISSION` | `emission_type`, `status` | string (`"psy_storm"`/`"emission"`), string (`"starting"`/`"ending"`) |
| `MAP_TRANSITION` | `actor`, `source`, `destination`, `visit_count`, `companions` | Character, string (level ID), string (level ID), number, Character[] |
| `IDLE` | `speaker`, `instruction` | Character, string |
| `WEAPON_JAM` | `actor` | Character |
| `SLEEP` | `actor`, `companions`, `hours` | Character, Character[], number |
| `RELOAD` | `actor` | Character |
| `TASK` | `actor`, `action`, `task_name`, `task_giver`, `companions` | Character, string, string, Character, Character[] |
| `CALLOUT` | `spotter`, `target` | Character, Character |
| `TAUNT` | `taunter`, `target` | Character, Character |

Character keys recognized by the serializer: `victim`, `killer`, `actor`, `spotter`, `target`, `taunter`, `speaker`, `task_giver`. Array key: `companions`.

### Event Text: Templated, Not Stored

```
LUA SAVE (stored)                PYTHON (constructed on read)
━━━━━━━━━━━━━━━━                 ━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ seq = 23,                      MemoryEvent(
  timestamp = 380,                   seq=23,
  type = "DEATH",                    timestamp=380,
  context = {                        type="DEATH",
    victim = {                       context={
      game_id = "11111",               "victim": CharacterRef(...),
      name = "Petrov",                 "killer": {"name": "bloodsucker"}
      faction = "stalker" },         },
    killer = {                       text="Petrov was killed by      ← generated
      name = "bloodsucker" },               a bloodsucker"  
  }                              )
}
                                 # Python translates:
  no text field                  #   faction "stalker" → "Loner"
                                 # then templates text from context fields
```

Saves stay lean — just the facts. Text is cheap to regenerate.

### Lua Serialization Format

```lua
talker_memories["12467"] = {
    background = {
        traits = {
            "gruff, suspicious of outsiders",
            "protective of rookies despite harsh exterior",
            "chain smoker, fidgets when anxious",
        },
        backstory = "Former Ukrainian border guard...",
        connections = {
            { character_id = "55891", name = "Fanatic",
              relation = "mentored at Rookie Village" },
            { character_id = "88234", name = "Grip",
              relation = "old drinking buddy" },
        },
    },
    events = {
        { seq = 23, timestamp = 380, type = "DEATH",
          context = {
              victim = { game_id = "11111", name = "Petrov",
                         faction = "stalker" },
              killer = { name = "bloodsucker" },
          }},
        { seq = 24, timestamp = 395, type = "MAP_TRANSITION",
          context = {
              actor = { game_id = "12467", name = "Wolf",
                        faction = "stalker" },
              source = "l01_escape", destination = "l02_garbage",
              visit_count = 3, companions = {},
          }},
        -- ~120-200 bytes per event, no text field
        -- faction/location are technical identifiers, translated by Python
    },
    summary = {
        { seq = 3, tier = "summary", start_ts = 200, end_ts = 380,
          text = "Wolf witnessed several deaths near Cordon...",
          source_count = 10 },
    },
    digest = { ... },
    core = { ... },
}
```

---

## Four-Tier Compaction Cascade

### Tier Caps

| Tier | Cap | Size/Item | Total at Full | Created By |
|------|-----|-----------|---------------|------------|
| `events` | 100 | ~120–200 bytes | ~15 KB | Lua fan-out (mechanical) |
| `summary` | 10 | ~2,000 chars | ~20 KB | LLM (10 events → 1 summary) |
| `digest` | 5 | ~3,000 chars | ~15 KB | LLM (2 summaries → 1 digest) |
| `core` | 5 | ~4,000 chars | ~20 KB | LLM (2 digests/cores → 1 core) |
| `background` | 1 | ~1,500 chars | ~1.5 KB | LLM (on first speak) |
| **Total** | | | **~72 KB** | |

### Cascade Flow

```
event (100)     → 10 oldest events → 1 summary (LLM call)
                  Python renders events to text via templates,
                  feeds to compaction model

summary (10)    → 2 oldest summaries → 1 digest (LLM call)

digest (5)      → 2 oldest digests → 1 core (LLM call)

core (5)        → 2 oldest cores → 1 core (self-compacting, terminal)
```

### Memory Span at Full Capacity

```
100 raw events                                    = 100 events
+ 10 summaries  (each covering ~10 events)        = 100 events
+ 5 digests     (each covering ~20 events)        = 100 events
+ 5 cores       (each covering ~40+ events)       = 200+ events
                                                    ───────────
                                                    ~500+ events of history
```

An NPC at full capacity remembers the narrative arc of 500+ events — months of Zone life — in ~72 KB.

### What 100 Raw Events Covers

| Play Intensity | Events/Hour | Hours Covered | Sessions (~3h) |
|---|---|---|---|
| Light (exploring) | ~12 | ~8h | ~2–3 |
| Medium (combat zones) | ~20 | ~5h | ~1–2 |
| Heavy (constant action) | ~30 | ~3h | ~1 |

Most NPCs won't hit 100 — only those the player spends hours near. When they do, the oldest 10 compress into a summary before being evicted.

### Compaction Model

The LLM used for compaction is configurable independently from the dialogue model:
- **Fast/cheap model** (default) — good enough for summarization
- **Local model** — zero-cost if available
- **Same as dialogue model** — ensures quality but more expensive

Compaction cost is negligible regardless of model (~800 input tokens + ~600 output per call).

### Budget Pool Batch Trigger

Rather than compacting each NPC individually on every write:

```
budget = num_over_threshold_npcs × memory_compact_batch

Over-threshold: NPC has more items in any tier than that tier's max.
Total excess = sum of (count_in_tier - tier_max) across all over-threshold NPCs.

Trigger: total_excess >= budget → compact ALL over-threshold NPCs.
```

### Conversation Witnesses (Chain Tracking)

From the [embedding design](Memory_Rework_Design.md): a set of NPC IDs that accumulates across an event chain, ensuring all witnesses get a compression check when the chain ends — even if they've moved away.

```
Lua → Python:  game.event { witnesses: [...], conversation_witnesses: [...] }
Python → Lua:  dialogue.display { ..., conversation_witnesses: [union so far] }
Lua → Python:  game.event (DIALOGUE) { witnesses: [proximity], conversation_witnesses: [bigger union] }
Python:         (no reaction) → chain ends → compression check for all IDs in set
```

| Field | Meaning | Used For |
|-------|---------|----------|
| `witnesses` | Who is **currently here** and perceives this specific event | Storing events per-witness |
| `conversation_witnesses` | Union of **everyone involved** across the whole chain | Compression check at chain end |

---

## Timestamp-Based Diff Reads

### The Problem: Redundant Memory in Context

When an NPC speaks multiple times in a session, each `get_memories()` call returns their full history. Without diff reads, the conversation accumulates N full memory dumps — mostly identical content.

```
Turn 1: Wolf speaks → get_memories(12467) → ~2K tokens (full)
  ...Python records 6 events to Wolf (combat, emission, no dialogue)...
Turn 7: Wolf speaks → get_memories(12467) → ~2K tokens (90% overlap)

WITHOUT diff:  4K tokens of memory in context, ~90% redundant
WITH diff:     2K + ~300 = 2.3K tokens, zero redundancy
```

### How Diff Reads Work

Every `get_memories()` response includes `as_of_timestamp` — the server game time at response. The LLM uses this as `from_timestamp` on subsequent reads of the same NPC.

```python
# Full read (first time):
get_memories(character_id="12467")
→ { as_of_timestamp: 340, tiers: { core: [...], digest: [...], summary: [...], events: [...] } }

# Diff read (subsequent):
get_memories(character_id="12467", from_timestamp=340)
→ { as_of_timestamp: 395, tiers: { summary: [overlapping], events: [new only] } }
```

### Timestamp Filtering on Compressed Tiers

Each tier carries timestamps inherited from source events:

| Tier | Timestamp | Filter Rule |
|------|-----------|-------------|
| `events` | Single `timestamp` | Include if `timestamp >= from_timestamp` |
| `summary` | `start_ts`, `end_ts` | Include if `end_ts >= from_timestamp` (overlaps) |
| `digest` | `start_ts`, `end_ts` | Include if `end_ts >= from_timestamp` |
| `core` | `start_ts`, `end_ts` | Include if `end_ts >= from_timestamp` |

Overlap semantics ensure the LLM gets the most granular view of what changed — new events in full, plus any compressed tier that covers the transition period.

### The Sawtooth Pattern

```
  Full read              Diff reads              Cleanup + refresh
  ────────              ──────────              ──────────────────
  │                     │      │                │
  ▼                     ▼      ▼                ▼
┌─────────┐  events  ┌────┐  events  ┌────┐  cleanup  ┌─────────┐
│ FULL    │ ───────► │DIFF│ ───────► │DIFF│ ────────► │ FULL    │
│ 2K tok  │          │300t│          │200t│           │ 2K tok  │
└─────────┘          └────┘          └────┘           └─────────┘
 Turn 1               Turn 7         Turn 12           Turn 20
 ts=0                 ts=340         ts=380            (after cleanup
                                                        evicts Turn 1)
```

When tool cleanup (provider-specific or manual) clears the original full read from context, the next read is a full read again. Then diffs resume. The system prompt instructs:

```
MEMORY READS:
When reading a character's memories:
1. If this is your FIRST read of this character in this session,
   call get_memories(character_id) with no timestamp — full read.
2. Note the as_of_timestamp in the response.
3. On subsequent reads of the SAME character, call
   get_memories(character_id, from_timestamp=<last_as_of_timestamp>)
   to get only what changed.
4. If a previous full read has been cleared from context (you can't
   see it anymore), do a full read again.
```

---

## Unified Store Operations DSL

### Principle: One Module, Two Callers

All memory store mutations go through a single `memory_store` Lua module. This module is called both **locally** (by Lua triggers for event fan-out) and **remotely** (by Python via WS for compaction results and background writes).

```
┌──────────────────────┐     ┌──────────────────────┐
│     Lua Triggers     │     │    Python Service     │
│  (event fan-out)     │     │  (compaction, bg)     │
└──────────┬───────────┘     └──────────┬───────────┘
           │ direct call                │ state.mutate.batch (WS)
           ▼                            ▼
    ┌─────────────────────────────────────────┐
    │         memory_store (Lua module)        │
    │                                          │
    │   :append(char_id, resource, items)      │
    │   :delete(char_id, resource, ids)        │
    │   :set(char_id, resource, data)          │
    │   :update(char_id, resource, ops)        │
    │   :query(char_id, resource, params)      │
    │                                          │
    │   Persistence: save/load via game files  │
    └─────────────────────────────────────────┘
```

### Read Side: `state.query.batch`

Extends the existing batch query DSL. New memory resources slot into the same `resource_registry`:

```json
{
  "t": "state.query.batch",
  "p": {
    "queries": [
      {
        "id": "wolf_events",
        "resource": "memory.events",
        "params": { "character_id": "12467" },
        "filter": { "timestamp": { "$gte": 340 } },
        "sort": { "timestamp": 1 },
        "limit": 100
      },
      {
        "id": "wolf_summaries",
        "resource": "memory.summaries",
        "params": { "character_id": "12467" },
        "filter": { "end_ts": { "$gte": 340 } },
        "sort": { "start_ts": 1 }
      },
      {
        "id": "wolf_background",
        "resource": "memory.background",
        "params": { "character_id": "12467" }
      }
    ]
  }
}
```

### Write Side: `state.mutate.batch`

A new WS topic for batched mutations. Four verbs:

| Verb | Purpose | Params |
|------|---------|--------|
| `append` | Add items to a list resource | `character_id`, `resource`, `data: [...]` |
| `delete` | Remove items by explicit IDs | `character_id`, `resource`, `ids: [...]` |
| `set` | Replace an entire resource | `character_id`, `resource`, `data: {...}` |
| `update` | Partial update with operators | `character_id`, `resource`, `ops: {...}` |

#### Wire Format

```json
{
  "t": "state.mutate.batch",
  "p": {
    "mutations": [
      {
        "op": "delete",
        "resource": "memory.events",
        "params": { "character_id": "12467" },
        "ids": ["1709001200000", "1709001200500", "1709001201000"]
      },
      {
        "op": "append",
        "resource": "memory.summaries",
        "params": { "character_id": "12467" },
        "data": [
          {
            "id": "sum_1709001200000",
            "tier": "summary",
            "start_ts": 1709001200000,
            "end_ts": 1709001500000,
            "text": "Wolf witnessed several deaths near Cordon...",
            "source_count": 10
          }
        ]
      },
      {
        "op": "set",
        "resource": "memory.background",
        "params": { "character_id": "12467" },
        "data": {
          "traits": ["gruff", "protective of rookies"],
          "backstory": "Former border guard...",
          "connections": []
        }
      }
    ]
  }
}
```

#### Partial Background Updates via `update`

The `update` verb uses mongo-style operators for surgical writes:

```json
{
  "op": "update",
  "resource": "memory.background",
  "params": { "character_id": "12467" },
  "ops": {
    "$push": { "traits": "haunted by recent losses" },
    "$pull": { "traits": "jovial and carefree" },
    "$push": { "connections": {
      "character_id": "99001", "name": "Marked One",
      "relation": "trusts after player saved his squad"
    }}
  }
}
```

### ID-Based Deletes: No Race Conditions

Deletes use **explicit IDs** rather than sort-based "delete oldest N" to eliminate TOCTOU race conditions:

1. Python reads events via `state.query.batch` → gets back items with IDs (the `seq` or `timestamp` keys)
2. Python compacts those specific events into summaries (LLM call)
3. Python sends mutation: "delete these exact IDs, append these summaries"

If new events arrived between steps 1 and 3 (from Lua fan-out), they have different IDs and are untouched. The Lua handler iterates `ids`, removes from the table by key — if an ID doesn't exist (already deleted, stale reference), silently skip. Idempotent by default.

### The Compaction Atomic Pattern

Every tier follows the same contract: **read with IDs → process → delete by those exact IDs + append results**.

```json
[
  { "op": "delete", "resource": "memory.events",
    "params": { "character_id": "12467" },
    "ids": ["seq_1", "seq_2", "...", "seq_10"] },

  { "op": "append", "resource": "memory.summaries",
    "params": { "character_id": "12467" },
    "data": [{ "id": "sum_1", "start_ts": 200, "end_ts": 380,
               "text": "...", "source_count": 10 }] },

  { "op": "delete", "resource": "memory.summaries",
    "params": { "character_id": "12467" },
    "ids": ["sum_old_1", "sum_old_2"] },

  { "op": "append", "resource": "memory.digests",
    "params": { "character_id": "12467" },
    "data": [{ "id": "dig_1", "start_ts": 100, "end_ts": 380,
               "text": "...", "source_count": 2 }] }
]
```

The cascade is just repeated application of that atomic pattern — no special-case logic per tier.

### Resources Covered

| Resource | `append` | `delete` | `set` | `update` | `query` |
|----------|:--------:|:--------:|:-----:|:--------:|:-------:|
| `memory.events` | ✓ (Lua fan-out) | ✓ (compaction) | — | — | ✓ |
| `memory.summaries` | ✓ (compaction) | ✓ (compaction) | — | — | ✓ |
| `memory.digests` | ✓ (compaction) | ✓ (compaction) | — | — | ✓ |
| `memory.cores` | ✓ (compaction) | ✓ (self-compact) | — | — | ✓ |
| `memory.background` | — | — | ✓ (first write) | ✓ (trait evolution) | ✓ |

Note: `memory.events` append is exclusively Lua-side (fan-out). Python only deletes events (after compaction). The `delete` verb needs zero query machinery — just key lookup in a table. All filter/sort/limit stays on the read side.

---

## Event Flow

### Core Principle

> Lua records the *facts* (event fan-out to witnesses). Python compresses the *old* (compaction cascade via store DSL). The LLM reads memories and generates *dialogue*.

### Event Recording (Lua Fan-Out, No WS Roundtrip)

When an event occurs:

1. Trigger fires in Lua, identifies witnesses (nearby NPCs)
2. Lua's `memory_store` module appends the structured event to **each witness's** `events` list
3. For new witnesses (no memory entry yet), creates entry and backfills from `global_event_buffer`
4. Lua enforces tier cap (oldest-eviction if over 100 events)
5. Lua publishes the event to Python via WS (for dialogue processing)
6. No WS roundtrip needed for storage — works even when Python is down

Fan-out runs in Lua so events are never lost due to service disconnection. Python receives the event for dialogue generation but does not own the write path.

### Global Events: Dual-Write + Backfill

Global events (emissions, psy storms) use a **dual-write** strategy, all in Lua:

1. **For existing NPCs**: Lua writes the global event into each existing NPC's `events` list — like any personal event
2. **For the backfill buffer**: Lua also appends to `global_event_buffer` (cap: 30) for NPCs not yet encountered
3. **On first contact** (witness path or squad discovery): creates memory entry and backfills globals before writing the triggering event

### Memory Entry Creation: Two Paths

| Path | Trigger | Events Created | Who |
|------|---------|----------------|-----|
| **Witness path** | Event recording (Lua fan-out) | Global backfill + triggering event | Every witness |
| **Squad discovery path** | `get_character_info` tool call → Lua mutation | Global backfill only | Squad members not yet seen |

---

## Speaker Selection

### Inline Selection (Single LLM Call)

Speaker selection and dialogue generation happen in **one conversation turn** — no separate LLM call. Before appending the event message, Python pre-fetches context that helps the LLM make an informed speaker choice:

**Pre-fetch batch** (Python → Lua, single `state.query.batch`):

| Sub-query | Purpose | Notes |
|-----------|---------|-------|
| `query.world` | Location, time, weather, emission, faction standings, player goodwill | Scene-setting + social context |
| `query.characters_alive` | Dead story NPCs (~130 unique IDs) | World state: who's been killed |
| `memory.background` per candidate | Traits from each candidate's `Background` | May be `null` for NPCs never spoken as |

This pre-fetch is cheap — one WS roundtrip, no LLM calls.

### Event Message Structure

The event message includes everything the LLM needs to pick a speaker **and** generate dialogue:

```
[user] Event: bloodsucker killed Petrov near Cordon.
       Game time: Day 47, 14:30. [timestamp: 380]

       Candidates:
         - Wolf (id: 12467, Loner, Experienced)
           Traits: gruff, protective of rookies, chain smoker
         - Fanatic (id: 55891, Loner, Trainee)
           Traits: [none — no background yet]

       World: Cordon, overcast, light rain.
       Dead story NPCs: Sidorovich, Hip.
       Faction standings: Loner↔Duty: Neutral, Loner↔Freedom: Allied,
         Duty↔Freedom: Hostile, Loner↔Bandit: Hostile, ...
       Player goodwill: Duty +1200 (Good), Freedom -300 (Neutral),
         Bandit -800 (Neutral), ...

[assistant]
  (picks Wolf — his protective trait + experienced rank
   make him the natural reactor to a rookie's death)
  → get_memories("12467")                    # read Wolf's memories
  → [optional: get_character_info("12467")]  # if no background
  → [generates dialogue as Wolf]
  → [optional: background("12467", "write", {...})]
```

Traits give the LLM personality-aware speaker selection. An NPC with "protective of rookies" reacts differently to a rookie's death than one with "mercenary, only cares about money." If an NPC has no background yet, the LLM can still pick them — it just has less to go on.

### Why Not a Separate Speaker Selection Call?

The current system uses 2 LLM calls: one to pick the speaker, then another to generate dialogue. Merging them into one turn:

- **Halves LLM cost** per event (1 call instead of 2)
- **Lower latency** — no second roundtrip
- **Speaker choice is contextual** — the LLM sees memories and world state before committing, rather than picking blind from a list

The tradeoff: the LLM may call `get_memories` for a speaker it ends up not using. In practice this is rare — the candidate list is small (2-5 NPCs) and the LLM commits to its initial pick.

---

## Faction Relations & Disguise

### Faction Standings (Dynamic Matrix)

The game engine exposes a full faction×faction relation matrix via `relation_registry.community_relation(faction_a, faction_b)` and player-specific goodwill via `relation_registry.community_goodwill(faction, AC_ID)`. Both are **dynamic** — they change during gameplay:

| Data | Changes When | Cadence |
|------|-------------|--------|
| **Faction×faction matrix** | Warfare territory shifts, storyline events, GAMMA modpack overrides | Infrequent but unpredictable |
| **Player goodwill** per faction | Quest completion, NPC kills, faction-specific actions | Frequent (every quest turn-in) |

**9 factions** in the matrix: stalker, dolg, freedom, csky, ecolog, killer, army, bandit, monolith (plus renegade/greh/isg swapped in depending on player faction). That's 36 unique pairs + 9 goodwill values.

**Engine thresholds** (from `game_relations.script`):
- ≥ 1000 → Friends/Allied
- ≤ -1000 → Enemies/Hostile  
- Between → Neutral

Player goodwill tiers (PDA display): ≥2000 Excellent, ≥1500 Brilliant, ≥1000 Great, ≥500 Good, >-500 Neutral, >-1000 Bad, >-1500 Awful, >-2000 Dreary, else Terrible.

### Where Faction Data Lives

Both the faction matrix and player goodwill are added to `query.world` — fetched in the pre-fetch batch every event. No separate query needed.

```lua
-- Added to query.world handler:
result.faction_standings = build_faction_matrix()   -- 36 pairs → {"dolg_freedom": -1500, ...}
result.player_goodwill = build_player_goodwill()    -- 9 values → {"dolg": 1200, "freedom": -300, ...}
```

Python formats these into the event message:

```
Faction standings: Loner↔Duty: Neutral, Loner↔Freedom: Allied,
  Duty↔Freedom: Hostile, Loner↔Bandit: Hostile, ...
Player goodwill: Duty +1200 (Good), Freedom -300 (Neutral),
  Bandit -800 (Neutral), ...
```

This replaces the current static `FACTION_RELATIONS` dict in Python (`prompts/factions.py`) — the game engine is the source of truth, especially in warfare mode where relations shift dynamically.

### Token Cost

~250–350 tokens for the full matrix + goodwill in the event message. Fetched via WS (free), not LLM tokens beyond being part of the user message. Acceptable given the information density.

### Disguise System

The player can wear faction-specific outfits to appear as a different faction. The engine's `gameplay_disguise` module tracks a suspicion meter with 10 factors (outfit, weapon, distance, stay-time, inventory, etc.). At break-point (90), the player gets exposed.

**Current flow** (preserved in new design):
1. Lua's `game_adapter.create_character()` checks `gameplay_disguise.is_actor_disguised()`
2. If disguised: `Character.faction` = **true faction**, `Character.visual_faction` = **apparent faction**
3. Python's `describe_character()` appends `[disguised as Duty]`
4. Prompt builder detects disguise text → injects context note:
   - **Companion**: "you knew it was a disguise"
   - **Non-companion**: "you did NOT know it was a disguise — treat by apparent faction"

The disguise note is injected per-event into the prompt — no change needed for the new architecture.

### Companion Faction Tensions (RP vs. Gameplay)

In-game, companions are **not attacked** by enemy factions as long as the player isn't hostile with that faction. But for roleplay purposes, this gameplay mechanic should not suppress faction attitudes in dialogue. A Freedom companion who witnesses Duty soldiers should still express distaste — the LLM should use faction standings to inform tone, not combat rules.

The system prompt should note:
> Faction hostilities apply to your **attitude and dialogue**, not just combat. Even if you are travelling as a companion and are mechanically safe from a hostile faction, you still hold your faction's opinions about them.

---

## Character Backgrounds

### Structured Identity

Each NPC has a structured `Background` — not a markdown document. Fields support granular updates without string surgery.

```python
Background(
    traits=["gruff, suspicious of outsiders",
            "protective of rookies despite harsh exterior",
            "chain smoker, fidgets when anxious"],
    backstory="Former Ukrainian border guard. Entered the Zone three years ago "
              "after a debt crisis. Found purpose mentoring newcomers...",
    connections=[
        Connection(character_id="55891", name="Fanatic",
                   relation="mentored at Rookie Village"),
        Connection(character_id="88234", name="Grip",
                   relation="old drinking buddy, mutual respect"),
    ]
)
```

### Generation Lifecycle

Backgrounds are generated when an NPC is **selected as speaker** — not when they merely witness events. The LLM calls `get_character_info` which returns squad members with their existing backgrounds (or `null`), then generates connected backstories for the squad in one turn.

```
NPC selected as speaker → background exists?
  │
  ├─ Yes → read and use for dialogue
  │
  └─ No  → get_character_info(id)
           → generate Background for speaker + null squad members
           → background(id, "write", {...})  for each
           → use for dialogue
```

### Trait Evolution

Over time, the LLM can update traits as experiences accumulate:

```python
# After witnessing 3 squad deaths:
background("12467", "update",
    field="traits",
    remove="jovial and carefree",
    add="haunted by loss, prone to dark humor as a coping mechanism")

# After player earns trust:
background("12467", "update",
    field="connections",
    add={"character_id": "99001", "name": "Marked One",
         "relation": "trusts after player saved his squad"})
```

### Unique NPCs vs. Generic NPCs

| NPC Type | Background Source | Editable by LLM? |
|----------|------------------|:-:|
| **Unique** (Sidorovich, Wolf, etc.) | Pre-written, seeded at game load | Connections only |
| **Generic** (random stalkers) | LLM-generated on first speak | Fully editable |

Unique NPC backgrounds seeded from committed Lua data file (`bin/lua/domain/data/unique_backgrounds.lua`), generated offline by developer tooling.

### Unique NPC Background Seeding

**Source data** (existing, keyed by story_id):
- `talker_service/texts/backstory/unique.py` — full backstory paragraphs (~60+ NPCs)
- `talker_service/texts/personality/unique.py` — trait adjective strings (matching set)
- `talker_service/texts/characters/important.py` — name, role, faction, area metadata

**Pipeline (offline, run once by developer, output committed to codebase):**

**Script 1: `tools/generate_unique_backgrounds.py`**
1. Reads all three source files, combines per story_id
2. Builds an LLM prompt: given personality + backstory + metadata, generate a structured `Background` (traits list, backstory paragraph, connections list)
3. Calls LLM API (any provider — this is a dev tool, not runtime), one batch prompt with all NPCs
4. Writes enriched backgrounds to `tools/unique_backgrounds_output/` as temp JSON files (one per story_id)

**Script 2: `tools/package_unique_backgrounds.py`**
1. Reads temp folder output
2. Generates a Lua module: `bin/lua/domain/data/unique_backgrounds.lua`
3. Format: `story_id → Background` as a Lua table of structured objects

```lua
-- bin/lua/domain/data/unique_backgrounds.lua (auto-generated, do not edit)
local BACKGROUNDS = {
    ["esc_2_12_stalker_wolf"] = {
        traits = {
            "gruff, suspicious of outsiders",
            "protective of rookies despite harsh exterior",
            "chain smoker, fidgets when anxious",
        },
        backstory = "Former Ukrainian border guard...",
        connections = {
            { story_id = "esc_2_12_stalker_nimble", name = "Nimble",
              relation = "fellow Cordon veteran, mutual respect" },
        },
    },
    ["esc_m_trader"] = {
        traits = { "shrewd businessman", "cynical but reliable" },
        backstory = "One of the Zone's longest-serving traders...",
        connections = {},
    },
    ...
}
return BACKGROUNDS
```

**Lua runtime (game load):**
1. Requires `domain.data.unique_backgrounds`
2. Iterates entries, resolves each story_id to numeric game_id via `story_objects.object_id_by_story_id[story_id]`
3. Seeds `Background` into memory store for each resolved NPC
4. Skipped if NPC already has a background (save data takes precedence over seed)

**Key properties:**
- Main Python service does NOT need to run for either script
- Output is committed — no runtime generation, no API cost at game time
- Lua owns the seed data, Python never touches unique backgrounds (only reads via tools)
- `story_objects` registry is available at game load (no need to be near NPCs)
- Connections use `story_id` in the seed file — Lua resolves to numeric `character_id` at load time

---

## Notable Zone Inhabitants (System Prompt)

### Why System Prompt?

The ~35 characterized unique NPCs (leaders, important figures, notable locals) are **static game data** — they don't change during a session. This makes them ideal for the system prompt:

1. **Cacheable** — every provider caches the system prompt prefix. Static data amortizes to near-zero cost after the first turn.
2. **Always available** — the LLM doesn't need to call a tool to know who Sidorovich is. This avoids unnecessary tool roundtrips when the LLM wants to reference a well-known character organically.
3. **Rank-gated** — the existing instruction "familiarity governed by rank" still applies. A novice won't cite Sakharov's research in conversation, but the LLM needs to *know about* him to decide not to.

### Replaces Vague Name-Dropping

The current `KNOWLEDGE_FAMILIARITY` section vaguely lists ~9 names:
> "Sidorovich, Barkeep, Arnie, Beard, Sakharov, General Voronin, Lukash, Sultan, Butcher etc."

This gives the LLM names but no context — it has to guess who these people are from pretraining data (unreliable for a modded game). The new design replaces this with a structured registry:

```
## Notable Zone Inhabitants

Leaders:
- General Kuznetsov — Military commander, Southern checkpoint
- General Voronin — Duty leader, Rostok base
- Lukash — Freedom leader, Army Warehouses
- Cold — Clear Sky leader, Great Swamps
- Sakharov — Ecologist lead researcher, Yantar
- Dushman — Mercenary leader, Dead City
- Sultan — Bandit boss, Garbage
- Charon — Monolith leader, Pripyat outskirts
...

Important figures:
- Sidorovich — Loner trader, Cordon. First contact for most newcomers.
- Barkeep — Neutral bar owner, Rostok. Information broker.
- Strelok — Legendary stalker, whereabouts unknown.
- Beard — Loner trader, Zaton. Runs the Skadovsk bar.
...

Notable locals:
- Wolf — Experienced Loner, Cordon. Mentors newcomers.
- Hip — Young Loner, Cordon. Amateur journalist.
- Owl — Trader, Yanov Station. Information dealer.
...
```

### Token Cost

~35 characters × ~20 tokens each ≈ **700 tokens**. With the existing system prompt sections (Zone geography, ranks, reputation, knowledge rules, tool definitions), total system prompt is ~3.5–4K tokens. This caches perfectly on all providers.

### What Stays Dynamic

**Dead NPC tracking** (`query.characters_alive`) remains in the per-event user message, not the system prompt. A character being dead is *dynamic state* — it changes during gameplay. The system prompt tells the LLM *who these people are*; the event message tells the LLM *which ones are dead*.

| Data | Where | Why |
|------|-------|-----|
| NPC registry (name, faction, role, description) | System prompt | Static — never changes within a session |
| Dead NPC status | Event message (from `query.characters_alive`) | Dynamic — NPCs die during gameplay |
| NPC backgrounds (traits, backstory, connections) | Tool call (`get_character_info`) | Per-speaker — only fetched when needed |

### Scope: Characterized vs. Technical IDs

Two distinct datasets exist:

| Dataset | Count | Content | Used For |
|---------|-------|---------|----------|
| `texts/characters/important.py` | ~35 | Name, faction, role, area, description | System prompt registry |
| `bin/lua/domain/data/unique_npcs.lua` | ~130 | Technical section IDs only | Lua-side `is_important_person()` checks (trigger chance override) |

Only the ~35 characterized NPCs go in the system prompt — the broader ~130 ID set is a Lua-side concern for trigger logic, not LLM knowledge.

### Area Filtering: Not Needed in System Prompt

The current `world_context.py` filters notable characters by area proximity when reporting dead NPCs. This filtering is **not applied** to the system prompt registry — a stalker can *know about* Lukash without being in Army Warehouses. Area filtering only makes sense for the dead-status lines (to avoid noise about deaths the NPC wouldn't have heard about).

### Gender

The STALKER engine has no explicit gender field on game objects. Gender reaches the LLM through three channels — one per character type:

**1. Unique NPCs: descriptions in pre-written texts (TALKER-controlled)**

The backstory/personality texts in `texts/personality/unique.py` and `texts/characters/important.py` are TALKER-specific data that we fully control. Gender is encoded in the description prose ("a young girl", "legendary stalker", etc.). Since the LLM uses these texts when generating unique NPC backgrounds, it picks up gender naturally — no runtime field needed.

**Voice consistency rule**: descriptions must match the engine's voice assignment. If the engine gives an NPC a male voice set, the text must not claim female — TTS would produce male vocals while the LLM writes female dialogue.

**Audit of old TALKER personality texts**: The previous TALKER `texts/personality/unique.py` described 5 NPCs as "a young woman". Engine voice verification shows only 2 are actually female:

| NPC | ID | Engine `snd_config` | Voice Set | Actually Female? |
|-----|-----|---------------------|-----------|:---------------:|
| Hip | `devushka` | `characters_voice\human\woman\` | `woman` | **Yes** ✓ |
| Anna | `stalker_duty_girl` | `characters_voice\human\woman\` | `woman` | **Yes** ✓ |
| Eidolon | `monolith_eidolon` | `characters_voice\human\monolith_3\` | `monolith_3` | **No** ✗ |
| Semenov | `yan_ecolog_semenov` | `characters_voice\human\ecolog_3\` | `ecolog_3` | **No** ✗ |
| Kolin | `zat_stancia_mech_merc` | `characters_voice\human\killer_3\` | `killer_3` | **No** ✗ |

Eidolon, Semenov, and Kolin personality texts should be corrected — their engine voice sets are male.

**2. Generic NPCs: optional `gender` field on `get_character_info`**

The `get_character_info` tool response includes an optional `gender` field, derived from `sound_prefix` on the Lua side:

```
sound_prefix == "woman"  →  gender: "female"
otherwise                →  gender: "male"
```

This is the **only place** gender is surfaced at runtime. It's not needed in events, speaker selection, or other queries — only when the LLM is about to generate a background for an NPC it hasn't spoken as before. The Lua query handler derives it from the same `sound_prefix` already fetched for TTS, and adds it to the response — it's **not** a field on the `Character` dataclass itself:

```lua
-- In get_character_info query handler (not on Character model):
local gender = "male"
if character.sound_prefix == "woman" then
    gender = "female"
end
-- always included in response
```

**3. Player gender (`female_gender` MCM → system prompt)**

The existing MCM toggle `female_gender` (boolean, default false) is already mirrored to Python config. In the new design, this goes directly into the system prompt as part of the player identity section:

```
The player character is [male/female].
```

This ensures the LLM uses correct pronouns when NPCs refer to the player in dialogue and memory compression.

**Summary: Where gender lives**

| Character Type | Gender Source | Mechanism |
|---------------|--------------|----------|
| **Player** | `female_gender` MCM toggle | System prompt |
| **Unique NPCs** (~35) | Pre-written description text | Baked into backstory/personality texts (TALKER-controlled) |
| **Generic NPCs** | `sound_prefix` → `gender` field | Always present on `get_character_info` response (not on Character dataclass) |

---

## Conversation Lifecycle

### Session Start (Game Load)

```
Game loads → Lua deserializes memory_store from save file
  Python starts → creates conversation with system prompt
  Python reads memory data from Lua via state.query.batch as needed
  Events get text regenerated from templates at read time
```

The conversation does NOT persist across game loads. The Lua memory store IS the persistence layer. The conversation is ephemeral context.

### During Gameplay

```
Event happens near player
  │
  ├─ Lua fan-out: appends event to each witness's memory (local, free)
  │   ├─ Creates entries + backfills globals for new witnesses
  │   └─ Publishes event to Python via WS for dialogue generation
  │
  ├─ Pre-fetch batch (Python → Lua, single state.query.batch):
  │   ├─ query.world              → location, time, weather, emission...
  │   ├─ query.characters_alive   → dead story NPCs
  │   └─ memory.background × N   → traits per candidate witness
  │
  └─ Append to conversation:
        [user] "Event: {describe_event}.
                Game time: {game_day}, {game_time}. [timestamp: {game_time_ms}]

                Candidates:
                  - {name} (id: {id}, {faction}, {rank})
                    Traits: {traits or 'none'}
                  - ...
                World: {location}, {weather}.
                Dead story NPCs: {dead_names}.
                Faction standings: {faction_matrix}.
                Player goodwill: {player_goodwill}."

      LLM responds (single turn, 1 LLM call):
        → (picks speaker from candidates based on event + traits)
        → get_memories(id)                     (full or diff read)
        → [optional: get_character_info(id)]   (if no background)
        → [generates dialogue text as speaker]
        → [optional: background(id, "write", {...})]

      Python extracts:
        → Speaker ID + dialogue text → dialogue.display to Lua
        → Background writes → state.mutate.batch to Lua memory store
        → Compaction when budget threshold exceeded (separate LLM call)
```

### Comparison with Current Flow

| Aspect | Current (2-call) | New (1-call) |
|--------|:-:|:-:|
| Speaker selection | Dedicated LLM call with personalities batch | Inline — traits in event message |
| Dialogue generation | Separate LLM call + 6-query batch | Same turn — tools fetch memories on-demand |
| LLM calls per event | 2 | 1 (+ pre-fetch batch, no LLM) |
| Batch queries per event | 2 (personalities, then memories+world) | 1 pre-fetch (world+alive+traits) |
| Latency | ~2× LLM roundtrip | ~1× LLM roundtrip + 1 WS roundtrip |
| Cost | ~2× tokens | ~1× tokens |

The pre-fetch replaces the current `_pick_speaker` batch (which fetched `store.personalities` for all candidates) with a lighter read of structured `Background.traits` — same data, structured storage instead of freeform personality files.

### Session End (Game Save)

```
Game saves → Lua serializes memory_store to save file →
  (existing save/load pattern, memory_store owns the data)

Conversation is NOT saved
memory_store IS the durable state
```

---

## Provider Optimization Layers

The core architecture works on any provider with tool calling. Optimizations layer on top:

```
┌──────────────────────────────────────────────────────┐
│                Standard Tool Layer                     │
│  get_memories, background, get_character_info          │
│  (works on ANY provider with tool calling)             │
├──────────────────────────────────────────────────────┤
│            Provider Optimization Layer                 │
│                                                        │
│  Anthropic:  cache_control on system prompt             │
│              clear_tool_uses (exclude get_memories)     │
│                                                        │
│  OpenAI:     Automatic prefix caching (≥1024t prefix) │
│              Manual history truncation (client-side)   │
│                                                        │
│  Gemini:     cachedContent API (if system prompt >32K) │
│                                                        │
│  Ollama:     Implicit KV cache (local)                 │
│                                                        │
│  Hosted:     OpenAI-compatible endpoint                │
│              Optimizations depend on backend            │
└──────────────────────────────────────────────────────┘
```

### Prompt Caching

The system prompt (~3.5–4K tokens of Zone rules, faction data, NPC registry, memory rules, tool definitions) is the cacheable prefix — identical across all turns within a session.

| Provider | Cache Mechanism | Discount | Developer Action |
|----------|----------------|----------|------------------|
| Anthropic | `cache_control: {"type": "ephemeral"}` on system message | 90% | Add annotation |
| OpenAI | Automatic for stable prefixes ≥1024 tokens | 50% | None |
| Gemini | `cachedContent` API with named object | Varies | Separate API call |
| Ollama | Implicit KV cache | N/A (local) | None |

### Tool Result Cleanup

Old `get_memories` results become stale as Python records new events between turns. Cleanup strategies:

| Provider | Mechanism | Implementation |
|----------|-----------|----------------|
| Anthropic | `clear_tool_uses` API, can exclude specific tools | Config: trigger at N tokens, keep last K, exclude `get_memories` |
| OpenAI / Others | Manual: Python prunes matched tool_call + tool_result pairs from history | Remove oldest tool pairs when context exceeds threshold |

---

## Save Size Analysis

### Per-Event Storage (Structured, No Text)

```lua
-- ~120-200 bytes per event in Lua serialization (varies by type):
{ seq = 23, timestamp = 380, type = "DEATH",
  context = { victim = { game_id = "11111", name = "Petrov",
              faction = "stalker" }, killer = { name = "bloodsucker" } } }
```

Compared to ~250 bytes with a text field — structured events store roughly twice the history in the same budget.

### Per-NPC at Full Capacity

| Tier | Count | Size | With Lua Overhead |
|------|-------|------|-------------------|
| `events` | 100 | ~15 KB | ~18 KB |
| `summary` | 10 | ~20 KB | ~25 KB |
| `digest` | 5 | ~15 KB | ~19 KB |
| `core` | 5 | ~20 KB | ~25 KB |
| `background` | 1 | ~1.5 KB | ~2 KB |
| **Total** | | **~72 KB** | **~89 KB** |

### Save Size by Play Style

| Play Style | NPCs with memory | Avg Size/NPC | Serialized Total | % of Typical Save |
|---|---|---|---|---|
| Light (2–3 hrs) | 30–50 | ~5 KB | ~200–300 KB | ~1–2% |
| Medium (8–10 hrs) | 100–200 | ~10 KB | ~1–2 MB | ~3–5% |
| Heavy (30+ hrs) | 300+ | ~15 KB | ~5–6 MB | ~8–10% |

Anomaly saves are typically 5–50 MB. Memory adds 1–10% — manageable.

---

## Cost Analysis

### Per-Session Cost by Model Tier

Assumes 100 dialogue turns, 15 background generation events, 5 compaction batches.

#### Premium Tier (With Prompt Caching + Cleanup)

| Dialogue Model | Compaction Model | Session Cost |
|---------------|-----------------|:---:|
| Claude Opus 4.6 | Haiku 4.5 | ~$10.50 |
| Claude Sonnet 4.6 | Haiku 4.5 | ~$2.30 |
| GPT-4o | GPT-4o-mini | ~$1.90 |

#### Mid Tier (No Caching/Cleanup)

| Dialogue Model | Compaction Model | Session Cost |
|---------------|-----------------|:---:|
| Claude Sonnet 4.6 | Haiku 4.5 | ~$8.10 |
| GPT-4o | GPT-4o-mini | ~$6.50 |

#### Budget Tier

| Dialogue Model | Compaction Model | Session Cost |
|---------------|-----------------|:---:|
| GPT-4o-mini | GPT-4o-mini | ~$0.45 |
| Gemini 2.0 Flash | Gemini Flash | ~$0.22 |
| DeepSeek V3 | DeepSeek V3 | ~$0.76 |

#### Hosted / Subscription

| Dialogue Model | Compaction Model | Session Cost |
|---------------|-----------------|:---:|
| Hosted endpoint model | Hosted endpoint model | $0 (subscription) |

### Compaction Is Negligible

| Compaction Model | Per Call | Per Batch (5 NPCs × 2 calls) |
|-----------------|---------|-------------------------------|
| Haiku 4.5 | ~$0.003 | ~$0.03 |
| GPT-4o-mini | ~$0.001 | ~$0.005 |
| Gemini 2.0 Flash | ~$0.0003 | ~$0.003 |

---

## Trigger Architecture: Consolidated Event Intent

### Principle: Lua Decides Everything, Python Only Generates Dialogue

In the current system, the store/react decision is split across three layers with ad-hoc flags. The new design consolidates all gating into the Lua trigger layer. Python receives **only** events that should generate dialogue — no filtering, no `_should_someone_speak()`.

### Flag Elimination

All trigger-event flags are removed. The `flags` dict on events disappears entirely for triggered events.

| Flag | Current Use | Replacement |
|------|------------|-------------|
| `is_silent` | Python gate: store but no dialogue | `chance = 0` → chance roll always fails → store-only |
| `is_idle` | Python routing to idle handler | `event.type == "IDLE"` (Python routes on type) |
| `is_callout` | Lua dedup against event store | `context.target_name` on recent CALLOUT events |
| `important_death` | Never read by Python; vestigial | **Remove entirely.** Victim importance is already inferable from `context.victim` character data (rank, unique NPC status). The separate `is_important` top-level flag (victim OR killer important) already controls the chance=100% override in Lua. |
| `target_name` | Callout dedup | Moved to `context` where it belongs |

Player input flags (`is_whisper`, `is_dialogue`) are unaffected — different flow entirely.

### Consolidated Trigger Flow

```
TRIGGER fires
  │
  ├─ enable == false → abort, no event created
  │
  ├─ anti-spam / cooldown → abort, no event created
  │
  ├─ witnesses = game_adapter.get_characters_near_player()  -- always
  │   (may augment: e.g. death adds killer if not already present)
  │
  └─ is_important OR chance_roll(trigger_mcm_key)
      ├─ fail (includes chance=0) → STORE ONLY
      │   └─ trigger.store_event(type, context, witnesses)
      │      (no WS publish, Python never sees this)
      │
      └─ pass → STORE + PUBLISH
          └─ trigger.publish_event(type, context, witnesses)
              → Python generates dialogue
```

The old three-state `radio_h` (On/Off/Silent) collapses into two controls:
- **`enable`** (checkbox) — Off = no event at all, On = event created
- **`chance`** (0–100 integer) — 0 = store-only (equivalent to old "Silent"), 100 = always dialogue

`is_important` is a **local variable** inside the trigger — computed from character data (player, companion, unique NPC, high rank). It short-circuits the chance roll so significant events always generate dialogue. It is **never sent on the wire**.

### Trigger API (`interface/trigger.lua`)

Two entry points replace the old `talker_event` / `talker_event_near_player` pair:

```lua
--- Store event in witness memory only (no dialogue).
function m.store_event(event_type, context, witnesses)
    -- create Event, fan out to witness memory stores, no WS publish
end

--- Store event + publish to Python for dialogue generation.
function m.publish_event(event_type, context, witnesses)
    -- create Event, fan out to witness memory stores, WS publish
end
```

**`talker_event_near_player` is decommissioned.** All triggers call `game_adapter.get_characters_near_player()` directly to get witnesses, then pass the list to `store_event` or `publish_event`. No wrapper — the game adapter is the utility function. This makes witness resolution visible and augmentable at the trigger level.

### Witness Resolution

`game_adapter.get_characters_near_player()` should read the MCM `witness_distance` setting **dynamically** (via `config.witness_distance()` getter), not as a static value captured at module load time. This ensures mid-game MCM changes take effect immediately.

**Trigger-specific augmentation** — triggers that need extra witnesses augment the list after fetching:

```lua
-- Death: add killer to witnesses (they remember it, even if far away)
local witnesses = game_adapter.get_characters_near_player()
local killer_nearby = killer and contains(witnesses, killer) or false
if killer and not killer_nearby then
    table.insert(witnesses, killer)
end
local context = { victim = victim, killer = killer, killer_nearby = killer_nearby }
-- killer_nearby lets LLM decide if killer should speak

-- Map transition: add all companions (travel party)
local witnesses = game_adapter.get_characters_near_player()
for _, companion in ipairs(game.get_companions()) do
    if not contains(witnesses, companion) then
        table.insert(witnesses, companion)
    end
end

-- Sleep: same pattern as map_transition (player + companions + nearby)

-- Emission: uses default witness_distance (same as all other triggers)
-- The 200m override is removed — emission events are written to every
-- NPC's memory via normal witness fan-out at default range.

-- Callout, taunt, idle: just game_adapter.get_characters_near_player(), no augmentation
```

### Chance Utility

A shared function rolls the chance check from a trigger's MCM setting:

```lua
-- In domain/service/chance.lua or similar:
local config = require("interface.config")

--- Roll a chance check against a trigger's MCM setting.
-- @param mcm_key  string  The MCM key for this trigger's chance (e.g. "triggers/death/chance")
-- @return boolean  true if the roll passes
function M.check(mcm_key)
    local pct = config.get(mcm_key)  -- integer 0-100
    if pct >= 100 then return true end
    if pct <= 0 then return false end
    return math.random(1, 100) <= pct
end
```

Every trigger calls `chance.check("triggers/<type>/chance")` — one pattern, no per-trigger reimplementation.

### Python Event Routing (Decommission `_should_someone_speak`)

With all gating moved to Lua, the Python event handler simplifies dramatically:

**Removed:**
- `BASE_DIALOGUE_CHANCE = 0.25`
- `_should_someone_speak(event, is_important)` — entire function deleted
- All `flags` reads: `is_silent`, `is_idle`, `is_callout`, `important_death`

**New routing** — pure type dispatch, every received event triggers dialogue:

```python
async def handle_game_event(event: GameEvent) -> None:
    # Every event that reaches Python was pre-approved by Lua.
    # No filtering, no chance roll, no flag inspection.
    if event.type == "IDLE":
        await _handle_idle_event(event)
    else:
        await _handle_standard_event(event)
```

The `flags` field can remain on the wire schema for backward compatibility but is ignored. New triggers should not populate it.

---

## MCM Settings

### Naming Convention

MCM settings are mod-namespaced under `"talker"`. Only the mod ID needs to be globally unique. Settings are fetched as `ui_mcm.get("talker/triggers/death/chance")`. Nested subsections use `sh = true`.

### Structure

Per-trigger subsections under `talker/triggers/`:

```
talker/
├── triggers/
│   ├── death/
│   │   ├── enable_player   check                     def: true
│   │   ├── cooldown_player input (seconds)            def: 90
│   │   ├── chance_player   input (0-100 %)            def: 25
│   │   ├── enable_npc      check                     def: true
│   │   ├── cooldown_npc    input (seconds)            def: 90
│   │   └── chance_npc      input (0-100 %)            def: 25
│   ├── injury/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 60
│   │   └── chance          input (0-100 %)            def: 25
│   ├── artifact/
│   │   ├── enable_pickup   check                     def: true
│   │   ├── cooldown_pickup input (seconds)            def: 30
│   │   ├── chance_pickup   input (0-100 %)            def: 100
│   │   ├── enable_use      check                     def: true
│   │   ├── cooldown_use    input (seconds)            def: 30
│   │   ├── chance_use      input (0-100 %)            def: 100
│   │   ├── enable_equip    check                     def: true
│   │   ├── cooldown_equip  input (seconds)            def: 30
│   │   └── chance_equip    input (0-100 %)            def: 100
│   ├── emission/
│   │   ├── enable          check                     def: true
│   │   └── chance          input (0-100 %)            def: 100
│   ├── idle/
│   │   ├── enable                    check            def: true
│   │   ├── cooldown                  input (seconds)  def: 600
│   │   ├── chance                    input (0-100 %)  def: 100
│   │   ├── enable_during_emission    check            def: true
│   │   ├── cooldown_during_emission  input (seconds)  def: 30
│   │   ├── chance_during_emission    input (0-100 %)  def: 100
│   │   ├── enable_during_psy_storm   check            def: true
│   │   ├── cooldown_during_psy_storm input (seconds)  def: 30
│   │   └── chance_during_psy_storm   input (0-100 %)  def: 100
│   ├── callout/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 30
│   │   └── chance          input (0-100 %)            def: 100
│   ├── taunt/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 30
│   │   └── chance          input (0-100 %)            def: 25
│   ├── reload/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 60
│   │   └── chance          input (0-100 %)            def: 10
│   ├── task/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 60
│   │   └── chance          input (0-100 %)            def: 10
│   ├── sleep/
│   │   ├── enable          check                     def: true
│   │   └── chance          input (0-100 %)            def: 100
│   ├── weapon_jam/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 60
│   │   └── chance          input (0-100 %)            def: 25
│   ├── anomaly/
│   │   ├── enable          check                     def: true
│   │   ├── cooldown        input (seconds)            def: 30
│   │   └── chance          input (0-100 %)            def: 25
│   └── map_transition/
│       ├── enable          check                     def: true
│       └── chance          input (0-100 %)            def: 100
├── memory/
│   ├── event_cap           input                      def: 100
│   ├── summary_cap         input                      def: 10
│   ├── digest_cap          input                      def: 5
│   ├── core_cap            input                      def: 5
│   ├── global_event_cap    input                      def: 30
│   ├── compact_batch       input                      def: 5
│   └── compact_model       select                     def: (fast)
└── service/                    (placeholder — existing MCM covers this)
    ├── api_key             input
    ├── model               select
    └── base_url            input
```

### Design Notes

- **All chance values are integers 0–100** (percent). `type = "input"`, not `type = "track"`. Clearer than float 0.0–1.0.
- **No global `base_dialogue_chance`** — every trigger has its own `chance`. The old 25% becomes the default for triggers that had it (death, injury, taunt, weapon_jam, anomaly).
- **`enable` (checkbox) is separate from `chance`** — `enable=false` aborts entirely (no event created). `chance=0` with `enable=true` means events are stored but never trigger dialogue (equivalent to the old "Silent" mode).
- **No `mode` radio** — the old three-state `radio_h` (On/Off/Silent) is replaced by `enable` + `chance`. Silent was just `chance = 0`. All 13 triggers now use the same uniform pattern: `enable` + `cooldown` + `chance`.
- **Idle during emission/psy_storm** — separate subsections override normal idle settings during environmental events. Defaults: 30s cooldown, 100% chance (rapid NPC chatter when everyone is pushed to safe zones). If the player speaks during an emission/psy_storm idle burst, NPC idle talk is temporarily suppressed (not "idle" mode while player is actively in dialogue).

---

## Open Questions

### 1. Context Growth Management Without Provider Cleanup
For providers without `clear_tool_uses`, how aggressive should Python-side history truncation be? Need to balance context freshness against losing older conversation turns.

### 2. Multi-Tenant Isolation
Memory store and tool handlers must be session-aware. Tenant A's conversation should access tenant A's memory, not tenant B's. Maps naturally to `SessionRegistry`.

### 3. Background Update Granularity
~~The `background("update")` action needs a clear schema.~~ **Resolved**: `update` verb uses `$push`/`$pull`/`$set` operators. `traits` and `connections` support add/remove; `backstory` uses `$set` for full replace.

### 4. Migration from Current System
Existing saves with single narrative blobs: current `narrative_memories[char_id].narrative` → becomes `core` tier entry. First game load after update detects old format and converts automatically.

### 5. Fallback When API Is Unreachable
- Event recording continues (Lua fan-out, no Python needed)
- Dialogue generation fails gracefully (no speech)
- Memory compaction pauses (events accumulate, tier caps enforce safety)
- On reconnection, LLM sees accumulated events in next `get_memories`

### 6. Mutation Atomicity
The `state.mutate.batch` operations are applied sequentially in one Lua call. If the game crashes mid-batch, partial writes are possible. In practice, saves won’t capture a half-applied batch since save happens on a separate callback. Worth monitoring but likely a non-issue.

### 7. ID Format for Delete
Events are keyed by `seq` (append-only counter). Summaries/digests/cores need stable IDs for delete-by-ID. Options: auto-generated from `tier_startTs`, or explicit `id` field in `CompressedMemory`. Current thinking: explicit `id` field set by Python at creation time.

---

## Comparison with Previous Designs

| Aspect | Embedding Design | Claude-Native | **Tools-Based (This)** |
|--------|-----------------|---------------|------------------------|
| Event storage | Structured objects | Markdown files | **Structured objects** |
| Metadata preserved | type, location, time | Lost in .md | **type, location, time, actors** |
| Event text in saves | Yes | Yes (markdown) | **No (templated on read)** |
| Lua save identifiers | N/A | N/A | **Technical (`l01_escape`, `stalker`)** |
| Memory store owner | Python | Python | **Lua (fan-out + save/load)** |
| Store operations | Custom per-resource | `memory_tool` API | **Unified DSL (`state.query/mutate.batch`)** |
| Delete strategy | N/A | N/A | **Explicit ID-based (no race conditions)** |
| Compaction tiers | 2 (mid + long) | 5 (event→concat→core) | **4 (event→summary→core)** |
| Compaction trigger | `conversation_witnesses` | Budget pool batch | **Both** |
| Retrieval method | Embedding scoring | `view /folder/` | **`get_memories(id, from_ts?)`** |
| Selection/filtering | Cosine + 4 coefficients | None | **Timestamp range only** |
| Character identity | Static lookup tables | `background.md` (markdown) | **Structured Background** |
| Provider lock-in | None (needs 90MB model) | Anthropic only | **None** |
| LLM tools | None (prompt injection) | `memory_tool` + 1 custom | **3 standard tools** |
| Embeddings | Yes (90MB RAM) | No | **No** |
| MCM knobs | 16 | ~10 | **~10** |

---

## Related Documents

- [Claude_Based_Memory.md](Claude_Based_Memory.md) — Previous Anthropic-locked design (superseded)
- [Memory_Rework_Design.md](Memory_Rework_Design.md) — Embedding-based design (superseded, structural ideas carried forward)
- [Memory_Compression.md](Memory_Compression.md) — Current system documentation
- [multi_store_memory_architecture.md](multi_store_memory_architecture.md) — Earlier proposal (not implemented)
