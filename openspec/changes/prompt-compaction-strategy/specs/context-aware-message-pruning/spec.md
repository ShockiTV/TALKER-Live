# context-aware-message-pruning (DELTA — BREAKING)

## Change

This spec is **superseded** by `prompt-compaction`. All requirements below are **REMOVED**.

## REMOVED Requirements

### ~~Pruning threshold and target~~
- ~~M1: Trigger at 75% of 128k (96k tokens)~~
- ~~M2: Reduce to ≤ 50% of 128k (64k tokens)~~

**Reason**: Replaced by MCM-configurable `prompt_budget_hard` threshold and always-prune dialogue tail. The old fixed 96k/64k thresholds assumed a 128k context window; the new approach is model-agnostic.

### ~~System message preservation~~
- ~~M3: Preserve ALL system prompt messages~~

**Reason**: The four-layer layout has exactly one system message at `_messages[0]` (always preserved). The old spec's plural "system messages" no longer applies.

### ~~Fixed retention counts~~
- ~~M4: Preserve last 5 dialogue pairs~~
- ~~M5: Preserve last 5 tool result messages~~

**Reason**: Replaced by always-prune dialogue tail with MCM-configurable `prompt_dialogue_pairs` (default 3). Tool messages no longer exist in the four-layer layout.

### ~~Priority-based removal~~
- ~~M6: Remove old tool results before old dialogue~~

**Reason**: No tool messages in the four-layer layout. Dialogue pair removal is strictly oldest-first.

### ~~Pre-call trigger~~
- ~~M7: Execute before each complete_with_tools() call~~

**Reason**: `complete_with_tools()` is replaced by `complete()` in the four-layer layout. The new compactor runs after prompt assembly, before `complete()`.

### ~~Logging format~~
- ~~M8: Log "Pruned {before}→{after} tokens (removed {N} tools, {M} dialogue)"~~

**Reason**: Replaced by phase-specific logging in `prompt-compaction` spec.

### ~~SHOULD/MAY requirements~~
- ~~S1-S3, M1-M2~~

**Reason**: Subsumed by `prompt-compaction` spec requirements.

## Migration

The file `llm/pruning.py` containing `prune_conversation()` SHALL be replaced by the new `compact_prompt()` function (may live in the same file or a new `compaction.py` in the dialogue/ package). All call sites SHALL be updated.
