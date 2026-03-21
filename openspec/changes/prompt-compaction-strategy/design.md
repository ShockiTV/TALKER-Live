## Context

The `cache-friendly-prompt-layout` change introduces a four-layer message structure for LLM calls:

| Slot | Role | Content | Stability |
|------|------|---------|-----------|
| [0] | system | Static dialogue rules (~150 tok) | Frozen for session |
| [1] | user | Context block (BGs + MEMs as Markdown) | Append-only, grows |
| [2] | assistant | "Ready." (~6 tok) | Frozen |
| [3+] | user/assistant | Dialogue turns (event instructions + responses) | Grows per event |

Two growth vectors are unbounded: the context block (`_messages[1]`) accumulates BG/MEM entries for every NPC encountered, and dialogue turn pairs (`_messages[3:]`) accumulate indefinitely.

**Critical insight**: Old dialogue turns are redundant. Each NPC response is injected as a witness event into the event store for all nearby characters, which feeds into narrative memories in the cached context block. Keeping old turns in `_messages[3:]` pays for the same information twice — once in the uncacheable dialogue tail, once (cheaper, cached) via witness injection in the context block. For a new speaker who wasn't present for those old events, old turns have zero value.

The dialogue tail is also always uncacheable: even appending one new turn shifts the prior turns relative to the prefix, breaking the cache match for all of them. Only the prefix (system + context block + ack) benefits from caching.

The existing `prune_conversation()` in `llm/pruning.py` was designed for the old multi-system-message layout and doesn't understand the four-layer structure or cache stability.

## Goals / Non-Goals

**Goals:**
- Always-prune dialogue tail to a fixed window (no budget check needed, just count-based)
- Budget-triggered context block rebuild as the only size-control phase
- Give users MCM control: dialogue pair retention count + hard token limit + retained NPC context count
- Replace the old `prune_conversation()` with four-layer-aware logic
- Mirror the three new MCM settings to Python via `MCMConfig`

**Non-Goals:**
- Budget-based dialogue pruning (always-prune eliminates the need for token estimation on the tail)
- Summarising dropped BGs (drop entirely, re-injectable later)
- Parsing MEM text for character references to decide retention
- Preserving old dialogue turns for a specific speaker
- Implementing Anthropic explicit `cache_control` headers
- Changing the four-tier storage compaction cascade (separate concern)

## Decisions

### Decision 1: Always-prune dialogue tail (no budget check)

Every turn, before the LLM call, the dialogue tail (`_messages[3:]`) is trimmed to keep only the last N user+assistant pairs, where N = `prompt_dialogue_pairs` MCM setting (default 3).

This runs unconditionally — no token estimation, no threshold comparison. It's a simple count-based trim:

```python
# Pseudocode
pairs = identify_dialogue_pairs(messages[3:])
if len(pairs) > N:
    keep = pairs[-N:]
    messages = messages[:3] + flatten(keep)
```

**Rationale**: Old dialogue turns are already captured via witness injection into the context block. They contribute zero unique information while being uncacheable. Keeping N=3 recent pairs provides conversational continuity (the LLM sees the last 2-3 exchanges to avoid repeating itself) without paying for stale history.

**N=0 is valid**: Users can set `prompt_dialogue_pairs = 0` to prune all dialogue history, relying entirely on the context block for conversational context. Useful for extreme cost optimisation or models with tiny context windows.

### Decision 2: Budget-triggered context block rebuild (hard limit only)

After dialogue trimming, if estimated tokens still exceed `prompt_budget_hard * 1000`, rebuild the `ContextBlock` keeping:

1. **Candidate items** (always kept) — BGs and MEMs for characters in the current event's `candidate_ids`
2. **Recent non-candidate items** — BGs and MEMs for the last K non-candidate NPCs by insertion order, where K = `prompt_context_keep` MCM setting (default 5). Insertion order is a recency proxy — the most recently encountered NPCs were added last.
3. **Static items** (always kept) — inhabitants, faction standings, info portions
4. **Everything else** — dropped

Replace `_messages[1]` with the new `render_markdown()` output.

This is the only budget-based phase. It fires when the context block itself grows too large (many unique NPCs with backgrounds over a long session).

**Rationale**: With always-prune, prompt size ≈ `ctx_block + 156 + 400N`. For N=3 (default), the dialogue tail is fixed at ~1200 tokens. Only the context block grows unboundedly, so the hard limit only guards against that vector.

**Why recency-based retention**: In STALKER you move through zones sequentially. NPCs you just interacted with are most likely to be cross-referenced ("Sidorovich mentioned you were looking for artifacts..."). NPCs from several zones ago are narratively stale. The `ContextBlock` append-only insertion order maps directly to encounter recency, making this trivial to implement without extra tracking.

### Decision 3: Three MCM settings

| MCM Key | Python Field | Type | Default | Min | Max | Purpose |
|---------|-------------|------|---------|-----|-----|---------|
| `prompt_dialogue_pairs` | `prompt_dialogue_pairs` | integer | 3 | 0 | 20 | Dialogue pairs to keep per turn |
| `prompt_budget_hard` | `prompt_budget_hard` | integer (thousands) | 16 | 4 | 128 | Context block rebuild threshold |
| `prompt_context_keep` | `prompt_context_keep` | integer | 5 | 0 | 20 | Non-candidate NPC contexts to retain after rebuild |

`prompt_dialogue_pairs` and `prompt_context_keep` are plain integers. `prompt_budget_hard` is in thousands of tokens for MCM UX.

All three settings are intuitive count-based knobs (or a token budget that maps to NPC count):
- `prompt_dialogue_pairs = 3` → keep last 3 exchanges
- `prompt_context_keep = 5` → keep context for 5 recent NPCs beyond the candidates
- `prompt_budget_hard = 16` → rebuild when context block exceeds ~16k tokens

The hard limit default of 16 (= 16k tokens) means:
- Context block can grow to ~15k tokens before rebuild triggers
- That's ~35+ unique NPCs with backgrounds and memories
- Most sessions (1-2 hrs) never hit this
- Ollama users with 8k context can lower to 6-8
- GPT-4.1 users can raise to 32+ for maximum context richness

The context keep default of 5 means:
- After rebuild, ~1500-2500 tokens of non-candidate context retained (5 NPCs × 300-500 tok each)
- Players who want aggressive pruning set to 0 (candidates only)
- Players who want generous retention set to 15+

### Decision 4: `ContextBlock.rebuild_for_candidates()` method

The `ContextBlock` gains a single method for the hard-limit phase:

```python
def rebuild_for_candidates(
    self,
    candidate_ids: set[str],
    keep_recent: int = 5,
) -> "ContextBlock":
    """Return a new ContextBlock keeping items for candidates + recent NPCs.
    
    Retains (in priority order):
    1. BackgroundItems/MemoryItems where char_id is in candidate_ids
    2. BackgroundItems/MemoryItems for the last `keep_recent` non-candidate
       NPCs by insertion order (most recently added = most recently encountered)
    3. StaticItems (inhabitants, factions, info portions) — always kept
    
    Everything else is dropped.
    Returns a NEW ContextBlock (the original is not mutated).
    """
```

Returns a new instance (consistent with append-only contract). The caller replaces `self._context_block` and updates `_messages[1]`.

### Decision 5: compact_prompt() interface

```python
def compact_prompt(
    messages: list[Message],
    context_block: ContextBlock,
    candidate_ids: set[str],
    dialogue_pairs: int,     # from MCM (already plain integer)
    hard_limit: int,         # tokens (already multiplied from MCM thousands)
    context_keep: int,       # from MCM (non-candidate NPCs to retain)
) -> tuple[list[Message], ContextBlock, bool]:
    """Always-prune dialogue + budget-triggered context rebuild.
    
    Returns:
        (compacted_messages, compacted_block, cache_invalidated)
    """
```

Phase 1 (dialogue trim) always runs. Phase 2 (context rebuild) only if tokens > hard_limit after Phase 1. Phase 2 uses `context_keep` to retain recent non-candidate NPC contexts. Pure function — no mutation.

### Decision 6: Integration point in handle_event()

```
handle_event():
  1. Assemble prompt (inject BGs, MEMs, event instruction)
  2. compact_prompt(messages, block, candidates, N, hard)  ← HERE
  3. LLM complete() call
```

The compactor runs after full prompt assembly, before every LLM call. The dialogue trim is essentially free (no token estimation) so there's no cost to running it unconditionally.

Settings from config:
- `dialogue_pairs = config_mirror.get("prompt_dialogue_pairs")`
- `hard_limit = config_mirror.get("prompt_budget_hard") * 1000`
- `context_keep = config_mirror.get("prompt_context_keep")`

## Risks / Trade-offs

**[Trade-off] N=3 default drops most dialogue history** → Accepted. Witness injection already preserves the information in the context block. N=3 provides sufficient local conversational flow to avoid repetition. Users wanting richer conversational continuity can raise N up to 20.

**[Risk] Hard limit fires during area transition with many new NPCs** → One-time cache invalidation. New prefix starts accumulating cache hits on the next call. Acceptable.

**[Trade-off] Token estimation only needed for hard limit check** → `estimate_tokens()` is called once per turn (after dialogue trim). Much simpler than the old design which needed it for both phases.

**[Trade-off] MCM hard limit in thousands loses precision** → Acceptable. Difference between 16000 and 16500 is negligible for budget checks.

**[Benefit] Recency-based retention preserves narrative continuity** → NPCs you just traded with or walked past are most likely to be referenced in the next conversation. Keeping their context reduces "who?" moments where the LLM has no context for a recently-mentioned character.

**[Trade-off] prompt_context_keep=0 drops all non-candidate context** → Aggressive but valid. Users wanting maximum cost savings can set this alongside prompt_dialogue_pairs=0 for minimal prompts.

**[Benefit] Always-prune eliminates cache miss from reactive pruning** → In the old reactive model, occasional Phase 1 triggers shifted the dialogue tail and caused partial cache misses. Always-prune means the tail is always small and the prefix is always what gets cached. More predictable caching behaviour.
