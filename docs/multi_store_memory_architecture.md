# Multi-Store Memory & Reaction Architecture Proposal

## Overview

This document proposes a new architecture for TALKER Expanded's memory and reaction storage, introducing a third store (`reaction_store`) to complement the existing `event_store` and `memory_store`. The goal is to enable flexible retention policies, improved traceability, and more robust memory compression workflows.

---

## Store Structures

### 1. `event_store`
- **Purpose:** Stores all raw in-game events (typed, with context and witnesses).
- **Retention:** Pruned by age (default: 1 week, configurable via MCM).
- **Structure:**
  ```lua
  event = {
    type = "DEATH" | "ARTIFACT" | ...,
    context = { ... },
    game_time_ms = <timestamp>,
    world_context = "...",
    witnesses = { ... },
    flags = { ... },
  }
  event_store = { event, event, ... }
  ```

### 2. `reaction_store`
- **Purpose:** Stores all LLM-generated reactions (e.g., dialogue, taunts) in response to events.
- **Retention:** Pruned by age (default: off, configurable via MCM).
- **Structure:**
  ```lua
  reaction = {
    type = reaction.LLM_RESPONSE,  -- e.g., LLM_RESPONSE, TOOL_USE, etc.
    trigger_event = { ... },       -- Full event object (from event_store)
    response_message = "LLM output",  -- The actual LLM reply
    prompt_messages = {            -- List of Message objects (see below)
      { role = "system"|"user"|"assistant", content = "..." },
      ...
    },
    timestamp = <ms>,
    speaker_id = "12345",
    -- Optionally: LLM metadata (model, etc.)
  }
  reaction_store = { reaction, reaction, ... }
  ```

  **Message Structure (Python):**
  ```python
  class Message(BaseModel):
      role: Literal["system", "user", "assistant"]
      content: str
  ```

### 3. `memory_store`
- **Purpose:** Stores long-term, compressed narrative memory per character.
- **Retention:** No pruning (persistent, updated via compression algorithm).
- **Structure:**
  ```lua
  memory_store = {
    [character_id] = {
      narrative = "long-term memory string",
      last_update_time_ms = <timestamp>,
    },
    ...
  }
  ```

---

## Data Flow Diagram

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  event_store │────▶│ reaction_store│────▶│ memory_store │
└──────────────┘      └──────────────┘      └──────────────┘
      │                    │                     │
      │                    │                     │
      │                    ▼                     │
      │         [LLM generates response]         │
      │                    │                     │
      └────────────────────┴─────────────────────┘
                   │
                   ▼
        [Memory Compression Algorithm]
                   │
                   ▼
         Updates compressed narrative
```

- **Event Flow:**
  1. Game event is stored in `event_store`.
  2. LLM generates a reaction (e.g., dialogue) → stored in `reaction_store`.
  3. When enough new events/reactions accumulate, a memory compression algorithm runs, using:
     - Old compressed memory (from `memory_store`)
     - Related events (from `event_store`)
     - Related reactions (from `reaction_store`)
  4. The result is a new compressed narrative, stored in `memory_store`.

---

## Retention Policies

| Store           | Default Policy         | MCM Option? | Notes                  |
|-----------------|-----------------------|-------------|------------------------|
| event_store     | 1 week (by age)       | Yes         | Prune oldest first     |
| reaction_store  | Off (keep all)        | Yes         | Prune by age if set    |
| memory_store    | None (persistent)     | No          | Only updated, not pruned|

---

## Inputs to Memory Compression

The memory compression generator receives:
- **Old compressed memory** (from `memory_store`)
- **Related events** (from `event_store`)
- **Related reactions** (from `reaction_store`)

It applies an algorithm (LLM-based or otherwise) to produce a new narrative summary, which replaces the old entry in `memory_store`.

**Note:** The exact algorithm is out of scope for this proposal; only the data flow and store usage are specified.

---

## Summary

This architecture:
- Decouples raw events, LLM reactions, and compressed memory
- Enables flexible, independent retention policies
- Improves traceability and debuggability (full prompt context stored)
- Lays groundwork for advanced memory compression and replay features

---

*Drafted: 2026-01-31*
