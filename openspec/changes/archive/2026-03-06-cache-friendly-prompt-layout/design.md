## Context

The `ConversationManager` currently assembles LLM prompts with the system message rebuilt every turn (including dynamic weather/time/location/inhabitants), event details and candidate backgrounds as individual `[system]` messages (per the `deduplicated-prompt-architecture` design), and memories injected per-character via a `DeduplicationTracker`. This works but has three problems:

1. **Cache invalidation every turn** — The system prompt includes volatile world state (weather, time, location), so OpenAI's automatic prefix caching never activates (the first message changes every call).
2. **Multiple system messages break providers** — Ollama, some Gemini models, and budget OpenRouter endpoints reject or mishandle multiple `[system]` messages.
3. **No event filtering** — All events are injected globally, even when only a subset is relevant to the current step (picker doesn't need witness events; dialogue doesn't need events the speaker didn't witness).

OpenAI's prompt caching operates on 1024-token chunks from the start of the serialized message array. Only the longest byte-identical prefix is cached (50% input token discount). Anthropic uses explicit `cache_control` breakpoints. Both require stable prefixes.

## Goals / Non-Goals

**Goals:**
- Maximise LLM prefix cache hits by establishing a stable, append-only message prefix across turns
- Eliminate multiple `[system]` messages — use exactly one `[system]` (static rules) plus `[user]`/`[assistant]` for all data
- Remove volatile world state from system prompt; move weather/time/location into per-turn event instruction
- Filter events per step: picker gets zero witness events; dialogue gets only events where the speaker is a witness
- Replace the `DeduplicationTracker` + tagged system messages with a `ContextBlock` that tracks items internally and renders to Markdown

**Non-Goals:**
- Changing the compaction cascade logic (unchanged)
- Modifying the Lua-side wire protocol or event publishing (unchanged)
- Implementing Anthropic explicit `cache_control` headers (future optimisation)
- Changing the 4-tier memory store structure in Lua (unchanged)

## Decisions

### Decision 1: Four-layer message architecture

Every LLM call uses exactly this message structure:

| Position | Role | Content | Stability |
|----------|------|---------|-----------|
| 0 | `system` | Static dialogue rules only (~150 tokens) | Never changes within session |
| 1 | `user` | Context block: all BGs + all MEMs as Markdown | Append-only (grows, never rewritten except on compaction) |
| 2 | `assistant` | `"Ready."` | Never changes |
| 3+ | `user`/`assistant` | Dialogue turns (picker ephemeral, dialogue persistent) | Grows per event |

**Rationale**: The system message is tiny and stable. The context block user message starts at ~150 tokens (system) + grows with each new BG/MEM. Once it crosses 1024 tokens total prefix, every subsequent call gets automatic cache hits on the first chunk. The `"Ready."` ack establishes turn alternation so no provider chokes on consecutive user messages.

**Alternative rejected**: Keeping multiple `[system]` messages (current dedup design) — breaks Ollama/Gemini, no cache benefit over single-user-message approach since caching is prefix-based regardless of role tokens.

### Decision 2: ContextBlock data model with Markdown renderer

A new `ContextBlock` class stores items as typed Python dataclasses internally and renders them to Markdown on demand via `render_markdown()`. The class maintains set-based dedup indexes (`_bg_ids`, `_mem_keys`) and an ordered `_items` list.

```
ContextBlock
  _items: list[ContextItem]          # ordered by insertion time
  _bg_ids: set[str]                  # char IDs with backgrounds added
  _mem_keys: set[tuple[str, int]]    # (char_id, ts) pairs added
  
  add_background(char_id, name, faction, bg_text) → bool
  add_memory(char_id, name, ts, tier, text) → bool
  has_background(char_id) → bool
  has_memory(char_id, ts) → bool
  render_markdown() → str            # iterate _items in order, emit Markdown
```

The `render_markdown()` method iterates `_items` in insertion order, emitting BG entries as `## Name (Faction) [id:X]` headers and MEM entries as `[TIER] Name [id:X] @ts: text` lines. Since `_items` is append-only, the rendered output is byte-identical up to the last previously-rendered item — new items only add tokens at the end, preserving the prefix cache.

**Rationale**: Internal data model enables O(1) dedup lookups without parsing message content. Markdown output is token-efficient and universally readable by LLMs. The separate internal/render split means we never parse Markdown backward.

**Alternative rejected**: JSON context block — appending to a JSON array shifts closing tokens mid-prefix, breaking the cache on every append.

### Decision 3: Static-only system prompt

The system prompt contains timeless NPC dialogue rules:
- Zone setting, STALKER universe tone
- Dialogue length/style guidelines
- No weather, no time, no location, no inhabitants

Weather, time-of-day, and location are event-local facts and belong in the per-turn instruction (Layer 4). Notable inhabitants information moves to the context block as additional character entries.

**Rationale**: Any dynamic content in the system prompt breaks the cache from token 0 on every turn. The system prompt is the single most important thing to keep stable — it's the start of every prefix chunk.

### Decision 4: Event filtering per dialogue step

**Picker step**: The picker user message contains only the triggering event description (type, actor, victim, location) plus candidate IDs. No witness events are included — the picker doesn't need event history to choose who would react.

**Dialogue step**: The dialogue user message includes only events where the chosen speaker is listed as a witness. Events witnessed by other candidates but not the speaker are excluded.

Both steps include weather/time/location inline in the instruction message.

**Rationale**: Reduces per-call token count by 500-700 tokens typically (10 events × ~80 tokens, most irrelevant to the current step). Also improves cache hit rate — fewer varying events in the tail means more stable prefix.

### Decision 5: Context block compaction resets the block

When memory compaction triggers and rewrites memory items (replacing N raw entries with fewer compressed summaries), the `ContextBlock` is rebuilt from scratch:
1. Create new empty `ContextBlock`
2. Re-add all backgrounds (already known)
3. Re-add compacted memory items (new timestamps)
4. Replace `_messages[1]` with `render_markdown()`

This causes a one-time cache invalidation at the compaction boundary — acceptable since compaction is rare (threshold crossings only).

**Rationale**: Attempting to surgically edit the context block to replace memories in-place would produce a different byte sequence than append-only construction, defeating the purpose. Clean rebuild is simpler and the cache cost is amortised across many turns.

### Decision 6: World context data split

Current `build_world_context()` output is split:
- **Inhabitants**: Character entries added to context block as additional BG-like items (append-only, with alive/dead annotations)
- **Faction standings + player goodwill**: Added to context block as a static section (queried once per session, rarely changes)
- **Info portions** (Brain Scorcher, Miracle Machine): Added to context block (static facts)
- **Regional politics**: Included in per-turn instruction if location-relevant
- **Weather/time/location**: Included in per-turn instruction

**Rationale**: Things that don't change during a session go in the append-only context block. Things that change per event go in the instruction message. This maximises the stable prefix.

## Risks / Trade-offs

**[Risk] Context block grows unbounded** → Mitigated by existing compaction scheduler at context budget thresholds. When compaction fires, the block is rebuilt smaller.

**[Risk] "Ready." synthetic assistant message wastes tokens** → 6 tokens. Negligible. Required for clean user/assistant alternation.

**[Risk] Markdown rendering may produce slightly different output across Python versions** → Mitigated by using only string concatenation, no library dependencies. Pure `f-string` joins.

**[Trade-off] Compaction causes one-time cache invalidation** → Accepted. Compaction is infrequent and the rebuilt block immediately starts accumulating cache hits again.

**[Trade-off] Inhabitants in context block means they're in every call** → Accepted. They're small (~200 tokens for 10 characters) and static during a session. The cache benefit of keeping them stable outweighs the per-call cost.

**[Trade-off] Events not in context block (they're per-turn)** → This means events are never cached. Accepted — events are already small per step (~80-240 tokens) and filtered to only relevant ones, so the uncached cost is minimal.
