# Claude-Based Memory Architecture

> **Status**: Exploration / Early Design  
> **Started**: 2026-02-27  
> **Last Updated**: 2026-02-27  
> **Supersedes**: [Memory_Rework_Design.md](Memory_Rework_Design.md) (Embedding-Based Chunked Memory)

This document captures design thinking for an Anthropic-native memory architecture using Claude's `memory_tool`, prompt caching, context editing, and a five-tier compaction cascade. Rather than building a custom embedding retrieval engine, we use a virtual filesystem of per-NPC memories where Python handles all memory management (event recording, compaction) mechanically, and Claude only reads memories and generates dialogue.

---

## Motivation: Why Claude-Native Instead of Embeddings

### The Embedding Design Was Solving a Problem That Doesn't Exist

The embedding-based design doc built a sophisticated retrieval system (4 scoring coefficients, batch encoding, tier weights, 16 MCM knobs) to answer: "given limited context, which memories are most relevant?" But the per-NPC memory footprint is small:

| Scenario | Per-NPC Memory | Tokens (~3.5 chars/token) | % of 200K Context |
|----------|---------------|---------------------------|-------------------|
| Light play | 5–10 KB | ~1,400–2,800 | ~1.4% |
| Medium play | 15–30 KB | ~4,300–8,600 | ~4.3% |
| Heavy play | 50–70 KB | ~14,000–20,000 | ~10% |

At dialogue time, only one NPC's memories matter — the speaker's. Even at heavy play, their entire memory history fits in <10% of Claude's context window. **No filtering needed.**

### What Claude Brings That Embeddings Can't

| Capability | Embedding System | Claude memory_tool |
|-----------|-----------------|-------------------|
| **Relevance judgment** | Cosine similarity (semantic similarity ≠ importance) | True understanding of narrative importance |
| **Compression decisions** | Mechanical: char threshold triggers LLM summarize call | Judgment: Claude decides what to compress, what to promote, what to discard |
| **Memory curation** | Code-driven tier promotion (mid→long) | Python five-tier cascade compaction, Claude reads only |
| **Character generation** | Static lookup tables for personality/backstory | Claude generates and evolves traits from experience |
| **Cross-NPC awareness** | Impossible — each NPC scored independently | Claude can read squad members' backgrounds to weave connected stories |

### What Gets Eliminated vs. Added

```
ELIMINATED                              ADDED / CHANGED
──────────                              ──────────────
sentence-transformers (~90 MB RAM)      Anthropic API as LLM provider
all-MiniLM-L6-v2 embedding model       memory_tool handler (view/create/edit/delete)
Scoring formulas (4 coefficients)       Virtual filesystem backed by save data
Compression trigger (char threshold)    Context editing configuration
Compaction pipeline (3→1 merge)         Prompt caching (system prompt prefix)
batch_embed() infrastructure            Five-tier compaction cascade (Python-side)
retrieve_memories() algorithm           
16 MCM memory settings                  ~10 MCM settings
event_store (global ledger)             (still eliminated, same as embedding design)
```

---

## Architecture Overview

### Claude as Game Master, Not Individual NPC

One long-lived Anthropic conversation per game session (per tenant). Claude acts as the **game master/narrator** who voices individual NPCs, not as a separate Claude instance per NPC. The system prompt establishes this role, and each event message tells Claude which character to inhabit.

```
┌──────────────────────────────────────────────────────────────────┐
│                         GAME (Lua)                                │
│                                                                   │
│  Events → WS → Python service                                    │
│  Save/Load → marshal memory_store (dirs of .md files)            │
│  MCM: ~10 memory settings + API key                             │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     PYTHON SERVICE                                │
│                                                                   │
│  SessionRegistry (existing multi-tenant infra)                    │
│    └─ per-tenant:                                                 │
│         ├─ ConfigMirror              (exists)                     │
│         ├─ SessionContext / Outbox    (exists)                     │
│         └─ AnthropicConversation     (NEW)                        │
│              ├─ system_prompt         (prefix, cached)            │
│              ├─ messages[]            (growing conversation)      │
│              ├─ tools: [memory_tool, get_character_info]          │
│              └─ context_management    (editing + compaction)      │
│                                                                   │
│  MemoryFileSystem (virtual, backed by in-memory dict)             │
│    /memories/                                                     │
│      global_event_backfill/              (backfill for new NPCs)  │
│        001_emission.md                                            │
│      characters/                                                  │
│        12467/                            (single flat folder)     │
│          background.md                                            │
│          event_001.md ... event_025.md   (raw events)             │
│          concat_001.md ... concat_010.md (lossless joins)         │
│          summary_001.md ... summary_008.md (LLM compressed)      │
│          digest_001.md ... digest_005.md (LLM compressed)        │
│          core_001.md ... core_005.md     (terminal tier)          │
│        98234/                                                     │
│          ...                                                      │
└──────────────────────────────────────────────────────────────────┘
```

### Per-Tenant Connection + Prompt Caching

Each tenant (game client) gets its own Anthropic conversation thread via `SessionRegistry`. The system prompt is the prefix — identical across all turns — which makes it a perfect prompt caching target.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    system=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT,          # Zone rules, faction data, memory rules
            "cache_control": {"type": "ephemeral"},  # prompt caching
        }
    ],
    messages=conversation_messages,
    tools=[
        {"type": "memory_20250818", "name": "memory"},
        {"type": "custom", "name": "get_character_info", ...},  # init + squad + data
    ],
    context_management={
        "edits": [{
            "type": "clear_tool_uses_20250919",
            "trigger": {"type": "input_tokens", "value": 100000},
            "keep": {"type": "tool_uses", "value": 3},
            "exclude_tools": ["memory"],  # keep memory reads visible
        }]
    },
)
```

**Prompt caching**: The system prompt (~2–4K tokens of Zone rules, faction data, memory rules) is cached across all turns within a session. Every subsequent turn hits the cache — only the new event message and memory reads are fresh tokens.

**Context editing**: When the conversation grows past the threshold, old tool results (stale memory reads, past events) are automatically cleared. Memory tool calls are excluded from clearing so Claude always has its recent memory reads.

**Compaction**: Anthropic's server-side summarization of older conversation turns. Combined with context editing, this gives effectively infinite conversation length. (Note: distinct from the five-tier *memory* compaction handled by Python — see [Memory Compaction](#memory-compaction-python-side-mechanical).)

### Hat-Switching Within One Conversation

Claude plays all NPCs sequentially in the same conversation thread:

```
System prompt (~2-4K tokens):     ← CACHED (same every turn)
  Zone rules, faction data
  Memory tool definition
  Memory access rules

Turn 1 (Wolf speaks):
  [user] Event: death near Garbage.
         Candidates: Wolf (id: 12467, Loner, Experienced), Rookie (id: 11111, Loner, Trainee)
  [assistant] (picks Wolf) → reads /memories/characters/12467/* → generates dialogue

Turn 2 (Sidorovich speaks):
  [user] Event: player chat "Got any jobs?"
         Candidates: Sidorovich (id: 98234, Trader, Veteran)
  [assistant] (picks Sidorovich) → reads /memories/characters/98234/* → generates dialogue
```

The system prompt enforces memory isolation:

```
MEMORY ACCESS RULES:
- When speaking AS character {id}, ONLY reference memories from their folder
- You may READ other characters' backgrounds IF generating connected backstories
- You may WRITE only to the currently active character's folder and their
  squad members' folders (for backstory generation only)
- NEVER modify another character's event/concat/summary/digest/core files
```

---

## Memory Filesystem Layout

### Single Flat Folder Per NPC

Each NPC's memory is stored in a single flat folder with type-prefixed filenames. Sequence numbers are append-only and never reused.

```
/memories/
  global_event_backfill/                  # Backfill buffer for NPCs not yet encountered
    001_emission_<game_time>.md           # "An emission swept through the Zone"
    002_psy_storm_<game_time>.md
  characters/
    <character_id>/                        # Single flat folder per NPC
      background.md                       # Traits + backstory (Claude-generated or pre-written)
      event_001.md                        # Raw events (Python writes mechanically)
      event_002.md
      concat_001.md                       # Lossless join of 5 events (Python, no LLM)
      summary_001.md                      # LLM compression of 3 concats
      digest_001.md                       # LLM compression of 2 summaries
      core_001.md                         # LLM compression of 2 digests (terminal, self-compacting)
```

### Five-Tier Compaction Model

| Tier | Prefix | Max Files | ~Size/File | ~Total | Created By |
|------|--------|-----------|------------|--------|------------|
| Raw events | `event_` | 25 | 150 chars | 3,750 | Python (mechanical write) |
| Concatenations | `concat_` | 10 | 750 chars | 7,500 | Python (lossless join of 5 events) |
| Summaries | `summary_` | 8 | 2,000 chars | 16,000 | LLM (compresses 3 concats) |
| Digests | `digest_` | 5 | 3,000 chars | 15,000 | LLM (compresses 2 summaries) |
| Core | `core_` | 5 | 4,000 chars | 20,000 | LLM (compresses 2 digests or 2 cores) |

**Total per NPC at full capacity**: ~53 files, ~62K chars (~17K tokens, ~8.5% of 200K context)

### What Goes Where

| Content | Written By | Read By | Lifecycle |
|---------|-----------|---------|----------|
| `global_event_backfill/*.md` | Python (mechanical) | Python only (on first contact) | Oldest-eviction at cap; read once per NPC then forgotten |
| `event_*.md` | Python (mechanical, includes global events) | Claude (via folder view) | Consumed by concat compaction; Python enforces cap |
| `concat_*.md` | Python (lossless join) | Claude (via folder view) | Consumed by summary compaction; Python enforces cap |
| `summary_*.md` | LLM compaction model | Claude (via folder view) | Consumed by digest compaction; Python enforces cap |
| `digest_*.md` | LLM compaction model | Claude (via folder view) | Consumed by core compaction; Python enforces cap |
| `core_*.md` | LLM compaction model | Claude (via folder view) | Self-compacting when over cap; oldest content lost |
| `background.md` | Claude (generation) or pre-written for unique NPCs | Claude (via folder view) | Claude may update (trait evolution) |

---

## Event Flow: Mechanical Writes + Python Compaction

### Core Principle

> Python writes the *facts* (what happened). Python compresses the *old* (compaction cascade). Claude reads and generates *dialogue*.

### Event Recording (Python, Mechanical, No LLM Call)

When an event occurs:

1. Lua publishes event via WS with a list of witness IDs
2. For each witness, Python ensures a character directory exists — if not, **creates it and backfills global events** from `global_event_backfill/`
3. Python writes `event_{sequence}.md` to each witness's folder (the triggering event itself)
4. Python enforces tier cap on `event_*` files (oldest-eviction if over `memory_event_cap`)
5. Checks budget pool — runs batch compaction if threshold exceeded
6. No LLM call for event recording — this is free and instant (compaction may trigger LLM calls)

This is the **witness path** — the only path that writes non-global events. It handles both existing and never-seen NPCs uniformly.

```python
# Event arrives from Lua
def record_event(event: dict):
    content = describe_event(event)  # "Wolf was killed by a bloodsucker near Garbage"
    
    for witness_id in event["witnesses"]:
        # Create dir + backfill globals if this NPC has never been seen
        if not memory_fs.exists(f"/memories/characters/{witness_id}/"):
            backfill_globals(witness_id)
        
        # Write the triggering event
        path = f"/memories/characters/{witness_id}/event_{next_seq(witness_id, 'event'):03d}.md"
        memory_fs.create(path, content)
        enforce_tier_cap(witness_id, "event", config.memory_event_cap)
    
    # Check budget pool — run compaction if threshold exceeded
    maybe_compact_batch()


def backfill_globals(char_id: str):
    """Create character directory and copy global event backfill."""
    for bf in sorted(memory_fs.list("/memories/global_event_backfill/")):
        content = memory_fs.read(bf)
        memory_fs.create(f"/memories/characters/{char_id}/event_{next_seq(char_id, 'event'):03d}.md", content)
```

For a **never-seen witness**, the result is: `event_001.md` (backfilled emission), `event_002.md` (backfilled emission), `event_003.md` (**triggering event**). The triggering event becomes their first personal memory — the moment they entered the story.

**No event type filtering at storage layer.** The embedding design filtered "junk" event types (`ARTIFACT`, `ANOMALY`, `RELOAD`, `WEAPON_JAM`) from storage unless they triggered a dialogue reaction. This is **eliminated** — once an event passes Lua-side gates (cooldown, proximity, importance) and reaches Python, it is stored for **all** witnesses regardless of type. With Claude reading the full memory folder in 200K context, relevance judgment belongs to Claude at dialogue time, not to a hardcoded filter at write time. A weapon jam might be meaningless noise — or it might be the detail that makes Claude write a great line about the character's deteriorating equipment. The five-tier compaction cascade handles volume naturally: trivial events get compressed away in the concat→summary step while significant ones persist.

**Key invariant**: By the time Claude receives the event message, every witness already has a directory with the triggering event as an `event_*` file. Claude does not need to write it.

### Global Events: Dual-Write + Backfill

Global events (currently only `EMISSION` — covers both emissions and psy storms via `emission_type`) use a **dual-write** strategy:

1. **For existing NPCs** (already have a character directory): Python writes the global event directly into each existing NPC's memory folder as an `event_*` file — just like any personal event. The emission becomes a personal memory: they were there, they experienced it.

2. **For the backfill buffer**: Python also appends the event to `global_event_backfill/`. This is a small shared store that exists **only** to seed NPCs who haven't been encountered yet.

3. **On first contact** (NPC has no character directory yet): The **witness path** (event recording above) creates the directory and backfills globals before writing the triggering event. For squad members discovered later via `get_character_info`, the **squad discovery path** creates their directories and backfills globals only — they didn't necessarily witness the triggering event. See [Character Info Tool](#character-info-tool-get_character_info).

```python
# Global event (emission, psy storm)
def handle_global_event(event: dict):
    content = describe_event(event)
    
    # 1. Write to every existing NPC's memory folder
    for char_id in memory_fs.list_characters():
        path = f"/memories/characters/{char_id}/event_{next_seq(char_id, 'event'):03d}.md"
        memory_fs.create(path, content)
        enforce_tier_cap(char_id, "event", config.memory_event_cap)
    
    # 2. Append to backfill buffer (for NPCs we haven't met yet)
    backfill_path = f"/memories/global_event_backfill/{next_global_seq():03d}_{event['emission_type']}.md"
    memory_fs.create(backfill_path, content)
    enforce_global_cap(config.memory_global_event_cap)
    
    # 3. Check budget pool
    maybe_compact_batch()
```

After backfill, the global store is **not consumed** — other new NPCs may still need it. The backfill buffer is tiny (cap 30, covering months of play) and never read by Claude. It's purely a Python-side bookkeeping mechanism.

This means Claude never needs to read a separate `global_events/` directory during dialogue. Every NPC's memory folder is self-contained — personal events AND global events they lived through, all in one timeline.

### Directory Creation: Two Paths

An NPC's directory can be created through two independent paths:

| Path | Trigger | What `event_*` files are created | Who |
|------|---------|--------------------------------------|-----|
| **Witness path** | Event recording (Python, before Claude) | Global backfill + triggering event | Every witness of every event |
| **Squad discovery path** | `get_character_info` tool call (during Claude turn) | Global backfill only | Squad members not already seen |

"New NPC" is ambiguous — two orthogonal dimensions matter:

| State | Directory? | `background.md`? | What happens next |
|-------|:-:|:-:|---|
| Never seen | No | No | Witness path or squad discovery creates dir. |
| Witnessed events, never spoke | Yes | No | Has `event_*` files from witnessed events. No background needed until they speak. |
| Selected as speaker, no background | Yes | No | Claude generates background (+ squad) in the same dialogue turn, then speaks. |
| Selected as speaker, has background | Yes | Yes | Normal dialogue. Claude reads existing background. |
| Unique NPC (seeded) | Yes | Yes (pre-written) | Normal dialogue. Claude reads pre-written background. |

### Claude's Role: Read + Dialogue Only

Claude does NOT manage memory compaction. The system prompt instructs:

```
EVENT RECORDING:
The event described in the current message has ALREADY been written to the
character's memory folder as an event_* file. Do NOT write it again.
You do not need to view the folder just to see the current event — it is
in the message. Only view the memory folder when you want the character's
history to inform your dialogue.

MEMORY ACCESS:
Use `view` on the character's memory folder to read all memories in one call.
The folder contains event_*, concat_*, summary_*, digest_*, and core_* files
representing increasingly compressed layers of memory. Memory compaction is
handled automatically by the server — you should NEVER create, edit, or
delete these files. You MAY create or edit background.md only.
```

Claude's memory operations in a typical dialogue turn:

```
[user] Event: death near Garbage.
       Candidates:
         - Wolf (id: 12467, Loner, Experienced)
         - Fanatic (id: 55891, Loner, Trainee)

[assistant]
  (picks Wolf)
  → view /memories/characters/12467/          # returns ALL file contents in one call
  (no background.md? → get_character_info(12467) → generate backgrounds for Wolf + squad)

  (generates dialogue: "Another one down... the Zone doesn't care about names.")

  → create /memories/characters/12467/background.md
  → create /memories/characters/<squad_member>/background.md  (for members without one)
```

One `view` call returns all file contents inline — no pagination, no individual file reads. With ~53 files at ~62K chars, this fits comfortably in a single tool result. Claude's memory read is always exactly **1 tool call per NPC**.

> **Fallback if `view` can't return full contents**: If memory_tool's `view` on a directory only returns filenames (not contents), we add a second custom tool — `get_character_memory(character_id)` — that Python handles directly. It returns all tier files (`event_*`, `concat_*`, `summary_*`, `digest_*`, `core_*`) as structured content in one call. The `memory_tool` would still be used for per-NPC files Claude writes itself (`background.md`). Since Python manages all compaction tiers anyway, this is a natural split: Python-owned memory via custom tool, Claude-owned files via `memory_tool`.

### Memory Compaction (Python-Side, Mechanical)

All memory compaction is handled by Python as a preprocessing step before the dialogue turn. Claude never compacts.

#### Cascade Rules

When a tier exceeds its max after a write, the oldest files are consumed and produce one file in the next tier:

1. **event → concat**: 5 oldest `event_*` files joined into 1 `concat_*` (lossless concatenation, no LLM)
2. **concat → summary**: 3 oldest `concat_*` compressed into 1 `summary_*` (LLM call)
3. **summary → digest**: 2 oldest `summary_*` compressed into 1 `digest_*` (LLM call)
4. **digest → core**: 2 oldest `digest_*` compressed into 1 `core_*` (LLM call)
5. **core → core**: 2 oldest `core_*` compressed into 1 new `core_*` (self-compacting, terminal tier — the forgetting horizon)

Sequence numbers are append-only and never reused. Each cascade step reduces file count while progressively compressing older content.

#### Budget Pool Batch Trigger

Rather than compacting each NPC individually on every write, compaction uses a batch budget pool:

```
budget = num_over_threshold_npcs × memory_compact_batch

Over-threshold: NPC has more files in any tier than that tier's max.
Total excess = sum of (files_in_tier - tier_max) across all over-threshold NPCs.

Trigger: total_excess >= budget → compact ALL over-threshold NPCs.
```

This amortizes LLM compaction calls across many NPCs. A burst of events (e.g., combat) accumulates excess across witnesses, then one batch compaction pass processes everything.

#### Compaction Model

The LLM used for compaction is configurable independently from the dialogue model:

- **Haiku** (default) — fast, cheap, good enough for summarization
- **Local model** — zero-cost if available
- **Same as dialogue model** — ensures quality but more expensive

### Why This Is Safe: Memory Tool Is Client-Side

The memory_tool is entirely client-side. Claude calls `view` and `create`/`str_replace` (for `background.md` only) — and your Python handler executes them against the in-memory filesystem. There is no "Claude's cache" of the filesystem to break:

- Claude has no persistent filesystem state between `view` calls
- Context editing clears old `view` results from the conversation
- Python writing/compacting files between turns is invisible to Claude until the next `view`
- No parser invalidation, no cache breakage

Python can freely write event files and run compaction between Claude turns without interfering with Claude's view of the data.

---

## Retention Policies

Python enforces tier caps mechanically — every write is followed by a cap check:

```python
TIER_CAPS = {
    "event":   config.memory_event_cap,    # default 25
    "concat":  config.memory_concat_cap,   # default 10
    "summary": config.memory_summary_cap,  # default 8
    "digest":  config.memory_digest_cap,   # default 5
    "core":    config.memory_core_cap,     # default 5
}

def enforce_tier_cap(character_id: str, tier: str, cap: int):
    """Evict oldest files of this tier if over cap. Runs after every write."""
    prefix = f"{tier}_"
    files = sorted(f for f in memory_fs.list(f"/memories/characters/{character_id}/") if f.startswith(prefix))
    if len(files) > cap:
        for f in files[:-cap]:
            memory_fs.delete(f"/memories/characters/{character_id}/{f}")
```

| Tier | Cap | Purpose |
|------|-----|---------|
| `event_*` | 25 | Raw events per NPC (includes backfilled globals) |
| `concat_*` | 10 | Lossless event concatenations per NPC |
| `summary_*` | 8 | LLM-compressed summaries per NPC |
| `digest_*` | 5 | LLM-compressed digests per NPC |
| `core_*` | 5 | Terminal-tier memories per NPC (self-compacting) |
| `global_event_backfill/` | 30 | Backfill buffer for new NPCs |

Caps are hard limits — if compaction hasn't run (budget not exceeded) and a tier fills up, oldest files are evicted to make room. This prevents unbounded growth regardless of compaction scheduling.

---

## Speaker Selection

Speaker selection is handled **inline** within the same Anthropic conversation turn as dialogue generation. There is no separate call or model switch — Claude picks the speaker and generates dialogue in one turn.

### One-Turn Pattern

The event message includes a list of nearby NPC candidates with basic info (name, faction, rank). Claude evaluates who would most naturally react to the event and speaks as that character:

```
[user] Event: bloodsucker killed a rookie near Garbage.
       Candidates:
         - Wolf (id: 12467, Loner, Experienced)
         - Fanatic (id: 55891, Loner, Trainee)
         - Grip (id: 88234, Loner, Experienced)
       Location: Garbage. Time: 14:30.

[assistant]
  (evaluates candidates — Wolf is experienced and protective of rookies, most likely to react)
  → view /memories/characters/12467/                    # read Wolf's memories
  → [generates dialogue as Wolf]
```

**Why inline**: Claude already has full event context and Zone knowledge from the system prompt. Adding 2-3 lines of candidate info (name/faction/rank per NPC) costs ~50 tokens — negligible. A separate Haiku call for speaker selection would add latency for no meaningful savings. The candidates stay in the conversation as part of the event message, which gets summarized away by compaction like any other turn.

---

## Character Generation: background.md

### Single Document Per NPC

Each NPC has one `background.md` containing traits, backstory, and connections:

```markdown
# Wolf

## Traits
- Gruff, suspicious of outsiders
- Protective of rookies despite harsh exterior
- Chain smoker, fidgets when anxious

## Backstory
Former Ukrainian border guard. Entered the Zone three years ago
after a debt crisis. Found purpose mentoring newcomers at the
Rookie Village. Lost his partner Kolya to a Controller in Yantar
— still has nightmares about it. Joined Loner faction because
he trusts no one enough for organized groups.

## Connections
- Mentored Fanatic (id: 55891) at Rookie Village
- Shares a grudge with Butcher (Bandit) over a stolen stash
```

### Generation Lifecycle

```
NPC first encountered → Claude checks /memories/characters/{id}/

  ┌───────────────────────────────┐
  │ background.md exists?          │
  ├──────────┬────────────────────┘
  │ Yes      │ No
  │          ▼
  │   Claude generates:
  │   • Personality traits consistent with faction, rank
  │   • Backstory consistent with location, experience
  │   • Writes background.md
  │          │
  ▼          ▼
  Claude reads background.md → uses for dialogue
```

### Unique NPCs vs. Generic NPCs

| NPC Type | background.md Source | Editable by Claude? |
|----------|---------------------|-------------------|
| **Unique** (Sidorovich, Barkeep, etc.) | Pre-written, seeded at game load | Connections section only |
| **Generic** (random stalkers) | Claude-generated when warranted (not automatic) | Fully editable |

For unique NPCs, pre-written backgrounds are seeded into the filesystem when the game session starts (or on first encounter). Claude reads but doesn't overwrite the core Traits/Backstory sections. It may add to the Connections section as relationships form.

### Squad-Wide Backstory Generation

When Claude selects an NPC as speaker and they have no `background.md`, it calls `get_character_info(character_id)` — the single custom tool that handles initialization, squad discovery, and data retrieval in one call. See [Character Info Tool](#character-info-tool-get_character_info) for full details.

Background generation is automatic **when an NPC speaks** — not when they merely witness an event. Every event records `event_*` files to all nearby witnesses (cheap, no LLM), but only the selected speaker gets background investment. This is where the cost savings come from: witnesses accumulate event history silently, speakers get full characterization. When generating, Claude creates interconnected backgrounds for the entire squad in one turn:

```
[user] Event: bloodsucker killed a rookie near Garbage.
       Candidates:
         - Wolf (id: 12467, Loner, Experienced)
         - Fanatic (id: 55891, Loner, Trainee)
       Location: Garbage. Time: 14:30.

[assistant]
  (picks Wolf as speaker)
  → view /memories/characters/12467/                     # no background.md
  → get_character_info(12467)                            # tool call
  ← { character: {id: 12467, name: "Wolf", faction: "loner", rank: "Experienced", ..., background: null},
      squad_members: [
        {id: 55891, name: "Fanatic", faction: "loner", rank: "Trainee", ..., background: null},
        {id: 88234, name: "Grip", faction: "loner", rank: "Experienced", ..., background: "# Grip\n## Traits\n..."}] }
  # Wolf and Fanatic have no background (null) → generate. Grip already has one → respect it.
  → create /memories/characters/12467/background.md      # Wolf's background
  → create /memories/characters/55891/background.md      # Fanatic's, connected to Wolf & Grip
  → [generates dialogue for Wolf]
```

**Why tool retrieval instead of event payload**: Squad roster data (names, factions, ranks for all members) is heavy context. If embedded in the event message, it sits in the main conversation permanently — eating tokens on every subsequent turn. As a tool result, it's eligible for `clear_tool_uses` cleanup. The squad info served its purpose (background generation) and can be evicted from context on the next editing pass. Event payload stays lean.

The system prompt grants cross-write permission for backstory generation:

```
BACKSTORY GENERATION RULES:
When voicing an NPC who has no background.md:
1. Call get_character_info — it returns character + squad members with their
   existing backgrounds (null if none). No separate view calls needed.
2. WRITE background.md for the speaker AND all squad members whose background is null
3. Respect existing backgrounds — weave new backstories to connect with them
4. Create connected backstories — shared history, relationships, rivalries
5. Only write backgrounds for characters in the SAME squad
6. Do NOT base personality traits on event_* file content — a character's
   identity comes from their faction, rank, and location, NOT from events
   they witnessed. event_* files record what they EXPERIENCED, not who they ARE.
```

**Emission-contamination rule (point 6)**: At first contact, a new NPC's memory folder contains only backfilled global events (`event_*` files from emissions). Without this rule, Claude would read 5 emissions and generate every generic NPC as an "emission-haunted survivor." The instruction separates identity from experience: traits come from faction/rank/location context, memories come from `event_*` files.

Result: a squad with **interwoven history** generated on-the-fly, with squad roster data cleaned from context after use.

**Squad member timing**: `get_character_info` creates directories and backfills global events for squad members who haven't been seen yet (squad discovery path). These members get globals only — they weren't witnesses to the triggering event. If a squad member WAS a witness to the same event, their directory already exists from the witness path and they already have the event as an `event_*` file. When backgrounds are generated, they cover the squad in one turn — so when a squad member speaks later, their `background.md` already exists if Claude invested in the squad earlier.

**Witness-only NPCs** don't get backgrounds. They accumulate `event_*` files cheaply (mechanical writes, no LLM). If they're later selected as speaker, Claude generates their background at that point — with a richer event history to draw from than a fresh NPC would have.

### Trait Evolution

Over time, Claude can update `background.md` via `str_replace` as the NPC's experiences accumulate:

```
After witnessing 3 squad members die:
  str_replace in background.md:
    old: "jovial and carefree"
    new: "haunted by loss, prone to dark humor as a coping mechanism"
```

An NPC's personality **evolves from their experiences**. This is impossible with static lookup tables.

---

## Conversation Lifecycle

### Session Start (Game Load)

```
Game loads → Python starts →
  Creates Anthropic conversation with system prompt
  Memory filesystem loaded from save data
  Prompt cache primed on first API call
```

The Anthropic conversation does NOT persist across game loads. When the game reloads, Claude starts a fresh conversation and re-reads memory files. The memory filesystem IS the persistence layer. The conversation is ephemeral context.

### During Gameplay

```
Event happens near player
  │
  ├─ Python records event to witnesses' memory folders  (mechanical, free)
  │   ├─ Creates dirs + backfills globals for any never-seen witnesses
  │   └─ Runs compaction if budget pool threshold exceeded
  │
  └─ Append to Anthropic conversation:
        [user] "Event: {describe_event}.
                Candidates:
                  - {name} (id: {id}, {faction}, {rank})
                  - {name} (id: {id}, {faction}, {rank})
                Location: {location}. Time: {game_time}."
        
      Claude responds:
        → (picks speaker from candidates)
        → view /memories/characters/{id}/          (returns all files)
        → [optional: get_character_info if no background.md]
        → [generates dialogue text]
        → [optional: creates/edits background.md]
        
      Python extracts:
        → Speaker ID + dialogue text → dialogue.display to Lua
        → background.md writes applied to filesystem
```

### Context Growth Management

```
System prompt (~3K tokens)         ← ALWAYS CACHED
Turn 1: event + memory reads       ~2K tokens
Turn 2: event + memory reads       ~2K tokens
...
Turn 50: event + memory reads      ~2K tokens
                                   ─────────
Total after 50 events:             ~103K tokens

Context editing triggers at 100K:
  → Clears old tool results (stale view outputs)
  → Keeps last 3 tool uses + all memory tool calls
  → Claude continues with fresh context

Compaction (Anthropic server-side, for conversation turns):
  → Summarizes older conversation turns
  → "Earlier in this session, Wolf spoke about deaths near Garbage,
     Sidorovich complained about supplies, ..."
```

This gives effectively **infinite session length**. Hours of gameplay, hundreds of events, all in one conversation thread.

### Session End (Game Save)

```
Game saves → Python serializes memory filesystem to Lua table →
  Lua persists to save file (same as existing pattern)
  
Anthropic conversation is NOT saved — it's ephemeral
Memory files ARE the durable state
```

---

## Save Size Analysis

The memory filesystem is serialized into the Lua save file. Lua table serialization adds ~25% overhead (keys, quotes, escaping).

### Per-NPC Size at Full Capacity

| Tier | Files | Size/File | Raw Total | With Lua Overhead |
|------|-------|-----------|-----------|-------------------|
| `event_*` | 25 | 150 chars | 3,750 | 4,700 |
| `concat_*` | 10 | 750 chars | 7,500 | 9,400 |
| `summary_*` | 8 | 2,000 chars | 16,000 | 20,000 |
| `digest_*` | 5 | 3,000 chars | 15,000 | 18,800 |
| `core_*` | 5 | 4,000 chars | 20,000 | 25,000 |
| `background.md` | 1 | ~1,500 chars | 1,500 | 1,900 |
| **Total** | **54** | | **~64K** | **~80K** |

Most NPCs won't be full — only frequently-encountered ones fill all tiers.

### Save Size by Play Style

| Play Style | NPCs with dirs | Avg Size/NPC | Raw Total | Serialized | % of Typical Save |
|---|---|---|---|---|---|
| Light (2-3 hrs) | 30-50 | ~5K | 150-250 KB | ~200-300 KB | ~1-2% |
| Medium (8-10 hrs) | 100-200 | ~8K | 800K-1.6 MB | ~1-2 MB | ~3-5% |
| Heavy (30+ hrs) | 300+ | ~12K | 3.6+ MB | ~4-5 MB | ~8-10% |

Anomaly save files are typically 5-50 MB. The memory store adds 1-10% — manageable.

**Compaction reduces save size**: without the five-tier cascade, retaining all raw events would be ~150K+ per heavily-used NPC. Compaction compresses this to ~62K while preserving narrative depth.

**Comparison with current system**: the existing design stores one narrative blob per NPC (~1-3 KB each, ~100-600 KB total). This design stores ~5-20x more per NPC but with proportionally richer memory content.

---

## Cost Analysis

### Per-Dialogue Cost

| Component | Tokens (approx) | Cost (Sonnet) | Cost (Haiku) |
|-----------|-----------------|---------------|--------------|
| System prompt | ~3K (cached: 90% discount) | ~$0.0003 | ~$0.00006 |
| Event message | ~200 | ~$0.0006 | ~$0.0001 |
| Memory read (1 view call) | ~2K | ~$0.006 | ~$0.001 |
| Response (+ optional background.md) | ~500 out | ~$0.008 | ~$0.002 |
| **Per-dialogue total** | | **~$0.015** | **~$0.003** |

### Compaction Cost (Per Batch)

Compaction runs on the configured compaction model (default: Haiku). Cost per batch depends on how many NPCs need compaction:

| Component | Tokens (approx) | Cost (Haiku) |
|-----------|-----------------|---------------|
| Single compaction call (concat→summary, etc.) | ~2K in, ~1K out | ~$0.0005 |
| Typical batch (5 NPCs × 2 calls each) | ~30K total | ~$0.005 |
| Heavy batch (15 NPCs after combat) | ~90K total | ~$0.015 |

Compaction costs are negligible compared to dialogue — a heavy compaction batch costs the same as one dialogue turn.

### Per-Session Cost

| Dialogues/Session | Sonnet | Haiku |
|-------------------|--------|-------|
| 30 (light) | ~$0.45 | ~$0.09 |
| 100 (medium) | ~$1.50 | ~$0.30 |
| 300 (heavy) | ~$4.50 | ~$0.90 |

With prompt caching, the system prompt prefix (~3K tokens) hits cache on every turn after the first. This alone saves ~30-40% of input costs for short dialogues.

### Cost vs. Free Models

The current system uses free models (Gemini, OpenRouter free tier, etc.) — $0/session. This architecture introduces a non-zero cost floor. The tradeoff is:

| Aspect | Free Models | Claude + memory_tool |
|--------|-------------|---------------------|
| Cost | $0 | $0.09–4.50/session |
| Memory quality | Scoring formulas, mechanical compression | Five-tier compaction + Claude reads full history |
| Character depth | Static personality/backstory lookup | Dynamic generation, evolution, squad weaving |
| Reliability | Varies by provider | Consistent (Anthropic SLA) |
| Complexity | 16 MCM knobs, embedding model, scoring | ~10 MCM knobs, no local models (except optional compaction) |
| Provider lock-in | None (4 providers) | Anthropic only |

---

## Supported Models

The memory_tool is available on:

| Model | Tier | Best For |
|-------|------|----------|
| Claude Sonnet 4.6 | Mid | Dialogue generation (quality + cost balance) |
| Claude Haiku 4.5 | Fast | Bulk background generation, lightweight tasks |
| Claude Opus 4.6 | Premium | Best quality (expensive for routine dialogue) |

Recommendation: **Sonnet for dialogue.** Haiku available for bulk tasks. Opus reserved for special cases (if ever needed).

---

## MCM Settings

Simplified from the embedding design's 16 settings:

| MCM Key | Type | Default | Description |
|---------|------|---------|-------------|
| `memory_event_cap` | input | 25 | Max `event_*` files per NPC |
| `memory_concat_cap` | input | 10 | Max `concat_*` files per NPC |
| `memory_summary_cap` | input | 8 | Max `summary_*` files per NPC |
| `memory_digest_cap` | input | 5 | Max `digest_*` files per NPC |
| `memory_core_cap` | input | 5 | Max `core_*` files per NPC |
| `memory_global_event_cap` | input | 30 | Max files in `global_event_backfill/` |
| `memory_compact_batch` | input | 5 | Budget pool multiplier for batch compaction trigger |
| `memory_compact_model` | select | `haiku` | LLM model for compaction (Haiku, local, or dialogue model) |
| `anthropic_api_key` | input | — | Anthropic API key |
| `anthropic_model` | select | `claude-sonnet-4-6` | Model for dialogue generation |

Tier caps are rarely changed from defaults — the five-tier cascade is designed to balance file count, token usage, and information retention. The `memory_compact_batch` multiplier controls how aggressively compaction batches run (lower = more frequent, higher = larger batches).

---

## Persistence & Save Format

### In-Memory Representation

```python
# The virtual filesystem is a dict of path → content
memory_fs: dict[str, str] = {
    # Backfill buffer — only read by Python on first contact with a new NPC
    "/memories/global_event_backfill/001_emission.md": "An emission swept through the Zone at 14:30",
    
    # Per-NPC — single flat folder with type-prefixed filenames
    "/memories/characters/12467/background.md": "# Wolf\n\n## Traits\n...",
    "/memories/characters/12467/event_023.md": "Saw a bloodsucker kill a rookie near Garbage",
    "/memories/characters/12467/event_024.md": "An emission swept through the Zone at 14:30",
    "/memories/characters/12467/concat_005.md": "Wolf's squad moved through Garbage...",
    "/memories/characters/12467/summary_003.md": "Wolf witnessed several deaths...",
    "/memories/characters/12467/digest_002.md": "Wolf has survived months in the Zone...",
    "/memories/characters/12467/core_001.md": "Wolf is a hardened veteran of the Garbage region...",
    ...
}
```

### Serialization to Lua Save

On save, the dict is marshaled into a Lua table and persisted via `talker_game_persistence`. On load, it's reconstructed. The format is:

```lua
-- In save data:
talker_memory_fs = {
    ["global_event_backfill"] = {
        ["001_emission.md"] = "An emission swept through the Zone at 14:30",
    },
    ["characters"] = {
        ["12467"] = {
            ["background.md"] = "# Wolf\n\n## Traits\n...",
            ["event_023.md"] = "Saw a bloodsucker kill a rookie near Garbage",
            ["event_024.md"] = "An emission swept through the Zone at 14:30",
            ["concat_005.md"] = "Wolf's squad moved through Garbage...",
            ["summary_003.md"] = "Wolf witnessed several deaths...",
            ["digest_002.md"] = "Wolf has survived months in the Zone...",
            ["core_001.md"] = "Wolf is a hardened veteran of the Garbage region...",
        },
    },
}
```

### Migration from Current System

Existing saves with single narrative blobs can be migrated:

1. Current `narrative_memories[char_id].narrative` → becomes `core_001.md`
2. Current `event_store` events → become `event_*.md` for each witness
3. First game load after update detects old format and converts automatically

---

## Open Questions

### 1. Speaker Selection Model ✅ RESOLVED
**Decision**: Inline, one turn. Claude picks speaker and generates dialogue in the same turn. Candidates (name, faction, rank) included in event message — ~50 tokens, negligible cost. No separate Haiku call. See [Speaker Selection](#speaker-selection).

### 2. Background Generation Timing ✅ RESOLVED
**Decision**: Inline, same turn as dialogue. Background generation triggers when an NPC is **selected as speaker** — if Claude picks an NPC to voice and they have no `background.md`, Claude generates one (plus squad backgrounds) in the same turn. NPCs who merely witness events (receive `event_*` files but are never selected to speak) do NOT get backgrounds. This is where the savings come from: every event is recorded to all nearby witnesses, but only one NPC speaks per event. The speaking NPC gets full investment; the silent witnesses accumulate event history cheaply.

### 3. Context Editing Threshold
At what token count should context editing trigger? 100K is conservative (50% of 200K window). 150K gives more history but less headroom. Depends on typical session length and how much benefit older conversation context provides.

### 4. Compaction Strategy
Should we rely purely on Anthropic's server-side compaction, or also use context editing? The docs suggest using both: compaction for general context management, context editing for clearing specific tool result bloat. Need to test which combination works best for the event-heavy TALKER pattern.

### 5. Multi-Tenant Isolation
With the memory_tool being client-side, the filesystem handler must be session-aware. Tenant A's Claude conversation should access tenant A's memory filesystem, not tenant B's. This maps naturally to `SessionRegistry` but needs implementation attention.

### 6. Unique NPC Background Seeding ✅ RESOLVED

**Decision**: Two-stage offline pipeline → committed Lua seed file → Lua resolves IDs at game load.

**Source data** (existing, keyed by story_id):
- `talker_service/texts/backstory/unique.py` — full backstory paragraphs (~60+ NPCs)
- `talker_service/texts/personality/unique.py` — trait adjective strings (matching set)
- `talker_service/texts/characters/important.py` — name, role, faction, area metadata

**Pipeline (offline, run once by developer, output committed to codebase):**

**Script 1: `tools/generate_unique_backgrounds.py`** (uses main `.venv` with `anthropic` lib)
1. Reads all three source files, combines per story_id
2. Builds a Claude prompt: given personality + backstory + metadata, generate a structured `background.md` (Traits, Backstory, Connections sections)
3. Calls Claude API (key from `.env`), one batch prompt with all NPCs
4. Writes enriched backgrounds to `tools/unique_backgrounds_output/` as temp files (one per story_id)

**Script 2: `tools/package_unique_backgrounds.py`** (transforms to Lua-compatible format)
1. Reads temp folder output
2. Generates a Lua module: `bin/lua/domain/data/unique_backgrounds.lua`
3. Format: `story_id → background_md_content` as a Lua table of strings

```lua
-- bin/lua/domain/data/unique_backgrounds.lua (auto-generated, do not edit)
local BACKGROUNDS = {
    ["esc_2_12_stalker_wolf"] = "# Wolf\n\n## Traits\n...\n\n## Backstory\n...\n\n## Connections\n...",
    ["esc_m_trader"] = "# Sidorovich\n\n## Traits\n...",
    ...
}
return BACKGROUNDS
```

**Lua runtime (game load):**
1. Requires `domain.data.unique_backgrounds`
2. Iterates entries, resolves each story_id to numeric game_id via `story_objects.object_id_by_story_id[story_id]`
3. Seeds `background.md` into memory store for each resolved NPC
4. Skipped if NPC already has a `background.md` (save data takes precedence)

**Key properties:**
- Main Python service does NOT need to run for either script
- Output is committed — no runtime generation, no API cost at game time
- Lua owns the seed data, Python never touches unique backgrounds
- `story_objects` registry is available at game load (no need to be near NPCs)
- Claude-enriched: connections between NPCs extracted, traits expanded, Markdown structured

### 7. Fallback When API Is Unreachable
If the Anthropic API is down:
- Event recording continues (Python writes event files mechanically)
- Dialogue generation fails gracefully (no speech)
- Memory compaction pauses (events accumulate, Python tier caps enforce safety)
- On reconnection, Claude sees accumulated events in next `view`

---

## Squad API (Engine Analysis)

The STALKER Anomaly engine provides full squad membership support. Key findings from engine script analysis:

### NPC → Squad Lookup

```lua
local squad = get_object_squad(npc)  -- global in _g.script
-- Returns nil if NPC has no squad (group_id == 65535)
-- Returns the squad server entity (cse_alife_online_offline_group)
```

TALKER already wraps this as `talker_game_queries.get_squad(obj)`.

### Squad Object API

| Method/Property | Returns | Notes |
|---|---|---|
| `squad:squad_members()` | Iterator | Each item `k` has `.id` (number) and `.object` (server entity) |
| `squad:commander_id()` | number | ID of the squad leader |
| `squad:npc_count()` | number | Alive member count |
| `squad.player_id` | string | Faction name (`"stalker"`, `"bandit"`, `"duty"`, etc.) |
| `squad.id` | number | Squad's own unique ID |

### Online vs. Offline Members

The iterator yields server entities (`se_obj`) for ALL members. To get the client-side game object (needed for `character_name()`, `community()`, `rank()`, etc.):

```lua
for k in squad:squad_members() do
    local obj = db.storage[k.id] and db.storage[k.id].object  -- nil if offline
end
```

**Only online members are useful for TALKER.** Offline members have only an ID and section name — no character data. Since squads move together, members near the player are typically all online.

### Proposed Lua Query

New function for `talker_game_queries.script` — returns online, alive game objects only:

```lua
function get_squad_members(npc)
    local squad = get_object_squad(npc)
    if not squad then return nil end
    local members = {}
    for k in squad:squad_members() do
        if k.id ~= npc:id() then
            local obj = db.storage[k.id] and db.storage[k.id].object
            if obj and obj:alive() then
                table.insert(members, obj)
            end
        end
    end
    return members
end
```

Returns a plain list of game objects (same type as `get_nearby_npcs()`). The existing serializer can turn these into Character data for the wire — no special handling needed. Returns empty table if solo, nil if NPC has no squad.

### Character Info Tool: `get_character_info`

`get_character_info(character_id)` is the **single custom tool** alongside `memory_tool`. It serves as the entry point for initialization, squad discovery, and data retrieval — replacing what was previously split across `initialize_character()` and `get_squad_roster()`.

When Claude calls `get_character_info(character_id)`, the Python handler:

1. **Discovers online squad members** via `state.query` to Lua (calls `get_squad_members(npc)`)
2. **Creates directories + backfills globals** for squad members who don't have directories yet (squad discovery path — globals only, no triggering event)
3. **Reads `background.md`** for the character and each squad member (returns content or null)
4. **Serializes and returns** character + squad data using the existing Character serializer

Note: The calling character's directory **already exists** by this point — the witness path (event recording) created it before Claude was ever invoked. `get_character_info` does NOT create the calling character's directory.

```python
# Response format
{
    "character": {
        "id": 12467, "name": "Wolf", "faction": "loner",
        "rank": "Experienced", "reputation": "Neutral", ...,
        "background": null  # or string contents of background.md
    },
    "squad_members": [
        {"id": 55891, "name": "Fanatic", "faction": "loner", "rank": "Trainee", ...,
         "background": null},
        {"id": 88234, "name": "Grip", "faction": "loner", "rank": "Experienced", ...,
         "background": "# Grip\n## Traits\n..."}
    ]
}
```

- `squad_members` excludes the queried character (no duplication)
- Solo NPCs return an empty `squad_members` array
- NPCs without a squad return an empty `squad_members` array
- Uses existing Character serializer fields (name, faction, rank, reputation, etc.)
- `background` is `null` if no `background.md` exists, or the file contents as a string — Claude can see which members need backgrounds without separate `view` calls

---

## Related Documents

- [Memory_Rework_Design.md](Memory_Rework_Design.md) — Previous embedding-based design (superseded by this document)
- [Memory_Compression.md](Memory_Compression.md) — Current system documentation
- [multi_store_memory_architecture.md](multi_store_memory_architecture.md) — Earlier proposal (reaction_store, not implemented)
