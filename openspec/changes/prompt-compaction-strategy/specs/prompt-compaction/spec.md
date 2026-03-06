# prompt-compaction

## Purpose

Always-prune dialogue tail to a configurable fixed window plus budget-triggered context block rebuild, keeping the assembled prompt efficient while maximising LLM prefix-cache hits.

## Requirements

### Always-prune dialogue tail

The compactor SHALL trim the dialogue tail (`_messages[3:]`) to keep only the last N user+assistant pairs every turn, unconditionally.

#### Scenario: Trim to N pairs
- **WHEN** `compact_prompt()` runs with `dialogue_pairs=3`
- **AND** there are 12 dialogue turn pairs in `_messages[3:]`
- **THEN** the oldest 9 pairs are removed
- **AND** the last 3 pairs are retained
- **AND** `_messages[0:3]` (system, context block, ack) are untouched

#### Scenario: Fewer than N pairs exist
- **WHEN** there are 2 dialogue turn pairs and `dialogue_pairs=3`
- **THEN** no pairs are removed (all within the cap)

#### Scenario: N=0 removes all dialogue
- **WHEN** `dialogue_pairs=0`
- **THEN** all dialogue turn pairs are removed from `_messages[3:]`
- **AND** only `_messages[0:3]` remain (system, context block, ack) plus the current turn's instruction

#### Scenario: Orphaned messages
- **WHEN** a user message at the tail has no assistant response yet
- **THEN** it is treated as part of the newest pair and retained

### Hard limit — Context block rebuild

After dialogue trimming, the compactor SHALL check estimated tokens against the hard limit and rebuild the context block if exceeded.

#### Scenario: Under hard limit
- **WHEN** estimated tokens after dialogue trim are below `prompt_budget_hard`
- **THEN** context block is untouched
- **AND** `cache_invalidated` is `false`

#### Scenario: Over hard limit triggers rebuild
- **WHEN** estimated tokens after dialogue trim exceed `prompt_budget_hard`
- **THEN** `rebuild_for_candidates(candidate_ids, keep_recent=context_keep)` produces a new `ContextBlock`
- **AND** BackgroundItems and MemoryItems for candidates are retained
- **AND** BackgroundItems and MemoryItems for the last `context_keep` non-candidate NPCs by insertion order are retained
- **AND** all other character items are dropped
- **AND** StaticItems (inhabitants, factions, info portions) are always retained
- **AND** `cache_invalidated` is `true`

#### Scenario: context_keep=0 retains only candidates
- **WHEN** `context_keep=0` and a rebuild triggers
- **THEN** only candidate BGs/MEMs and StaticItems remain
- **AND** all non-candidate character items are dropped

#### Scenario: Insertion order determines recency
- **WHEN** the context block contains BGs for NPCs A, B, C, D, E (in insertion order) and only C is a candidate
- **AND** `context_keep=2`
- **THEN** C's items are retained (candidate)
- **AND** D and E's items are retained (2 most recently inserted non-candidates)
- **AND** A and B's items are dropped

#### Scenario: No candidates match
- **WHEN** `candidate_ids` is empty or no items match
- **THEN** the last `context_keep` NPCs' items by insertion order are retained
- **AND** StaticItems are retained

#### Scenario: Context block replacement
- **WHEN** a rebuild produces a new ContextBlock
- **THEN** `_messages[1].content` is replaced with `new_block.render_markdown()`
- **AND** the conversation's `_context_block` reference is replaced

### Pure function interface

The compactor SHALL be a pure function that does not mutate its inputs.

#### Scenario: compact_prompt signature
- **WHEN** `compact_prompt(messages, context_block, candidate_ids, dialogue_pairs, hard_limit, context_keep)` is called
- **THEN** it returns `(compacted_messages, compacted_block, cache_invalidated)`
- **AND** the original `messages` list and `context_block` are not modified

#### Scenario: Return types
- **WHEN** the function returns
- **THEN** `compacted_messages` is a `list[Message]`
- **AND** `compacted_block` is a `ContextBlock`
- **AND** `cache_invalidated` is a `bool`

### Integration point

The compactor SHALL run after full prompt assembly and before every LLM call.

#### Scenario: Trigger location in handle_event
- **WHEN** `handle_event()` has finished injecting BGs, MEMs, and the event instruction
- **AND** before calling `llm_client.complete()`
- **THEN** `compact_prompt()` is called with current messages, context block, candidate IDs, dialogue_pairs, and hard_limit

#### Scenario: Settings from config
- **WHEN** the compactor is invoked
- **THEN** `dialogue_pairs` is `config_mirror.get("prompt_dialogue_pairs")`
- **AND** `hard_limit` is `config_mirror.get("prompt_budget_hard") * 1000`
- **AND** `context_keep` is `config_mirror.get("prompt_context_keep")`

### Logging

The compactor SHALL log compaction actions at INFO level.

#### Scenario: Dialogue trim log
- **WHEN** dialogue pairs are trimmed and at least 1 pair was removed
- **THEN** log "Dialogue trim: kept {N}/{total} pairs"

#### Scenario: Context rebuild log
- **WHEN** the hard limit triggers a context block rebuild
- **THEN** log "Context rebuild: {before}→{after} tokens, {N} candidates + {K} recent retained"

#### Scenario: No-op log
- **WHEN** no pairs removed and no context rebuild
- **THEN** nothing is logged

## Non-Requirements

- ❌ Budget-based dialogue pruning (always-prune, no token check needed for dialogue)
- ❌ Summarising dropped background entries
- ❌ Parsing memory text to detect character references
- ❌ Per-speaker dialogue retention (oldest-first regardless of speaker)
- ❌ Soft token budget threshold (replaced by fixed dialogue pair count)

## Validation

### Unit Test Scenarios

1. **Under cap, under hard**: 2 pairs, 5k tokens → no changes, `cache_invalidated=false`
2. **Over cap, under hard**: 12 pairs, N=3, 8k tokens → trims to 3, no rebuild
3. **Over cap, over hard**: 12 pairs, N=3, 18k tokens → trims to 3, then rebuilds context with `context_keep=5`
4. **N=0**: All dialogue removed, only prefix + current instruction remain
5. **Pure function**: Original messages list unmodified after call
6. **context_keep=0**: After rebuild, only candidate items + statics remain
7. **context_keep=3**: After rebuild, candidate items + 3 most recent non-candidate NPC items + statics remain
6. **Static items preserved**: After rebuild, inhabitants/factions/info portions still present

### Integration Test Scenarios

1. **Long session simulation**: 50 events → verify prompt size stays bounded (~prefix + 3 pairs)
2. **Config change mid-session**: `prompt_dialogue_pairs` lowered to 1 → next event reflects immediately

## Dependencies

- `cache-friendly-prompt-layout` (provides four-layer message structure and `ContextBlock`)
- `talker-mcm` (MCM fields for dialogue pairs and hard limit)
- `python-config-mirror` (access to MCM settings in Python)

## Related Specs

- `context-aware-message-pruning` — superseded by this spec (BREAKING)
- `talker-mcm` — adds prompt_dialogue_pairs and prompt_budget_hard fields
- `python-config-mirror` — mirrors the new fields to Python
