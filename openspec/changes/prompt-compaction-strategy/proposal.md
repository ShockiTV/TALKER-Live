## Why

After the `cache-friendly-prompt-layout` change establishes the four-layer message structure (static system → context block → ack → dialogue turns), the prompt grows unbounded in two dimensions: the context block accumulates BG/MEM entries for every NPC encountered, and dialogue turn pairs accumulate indefinitely.

However, old dialogue turns are **redundant**: each NPC response is already injected as a witness event into the event store for all nearby characters, which feeds into narrative memories in the cached context block. Keeping old dialogue turns in `_messages[3:]` pays for the same information twice — once in the uncacheable tail, once in the cached prefix via witness injection. For a new speaker who wasn't present for those old events, old turns have zero value.

The always-prune approach eliminates this waste: dialogue turns are trimmed to a small fixed window (default 3 pairs) every turn, unconditionally. The only budget-based compaction is the hard limit, which triggers a context block rebuild when too many NPC backgrounds/memories accumulate.

Two MCM settings give users control: `prompt_dialogue_pairs` (how many recent dialogue turns to keep, default 3, 0 = none) and `prompt_budget_hard` (token threshold for context block rebuild, in thousands). This replaces the existing `context-aware-message-pruning` spec.

## What Changes

- **Two new MCM settings**: `prompt_dialogue_pairs` (integer, how many recent dialogue turn pairs to keep, default 3) and `prompt_budget_hard` (integer, thousands of tokens, hard limit triggering context block rebuild, default 16). Both exposed in the General Configuration section of the MCM.
- **Always-prune dialogue tail**: Every turn, before the LLM call, the dialogue tail (`_messages[3:]`) is trimmed to keep only the last N pairs (where N = `prompt_dialogue_pairs`). No token estimation needed — this is a simple count-based trim. The tail is uncacheable anyway, and old turns are already captured via witness injection.
- **Hard limit — Context block rebuild**: When estimated tokens still exceed the hard limit after dialogue trimming, rebuild the `ContextBlock` keeping only BGs and MEMs for current event candidates (plus static items like inhabitants/factions). One-time cache invalidation, re-injectable on demand.
- **Replaces existing pruning.py**: The current `prune_conversation()` in `llm/pruning.py` is replaced by the new compactor that understands the four-layer message layout.
- **MCM → Python config mirroring**: The two new MCM keys are synced to `MCMConfig` and used by `ConversationManager`.

## Capabilities

### New Capabilities
- `prompt-compaction`: Always-prune dialogue tail + budget-triggered context block rebuild with MCM-configurable settings

### Modified Capabilities
- `context-aware-message-pruning`: **BREAKING** — replaced by `prompt-compaction`. The old priority-based pruning (system messages sacred, oldest-first removal) is superseded by the always-prune + hard-limit strategy that understands the four-layer message layout. Hardcoded 128k/96k/64k thresholds replaced by MCM-configurable hard limit.
- `talker-mcm`: Two new settings: `prompt_dialogue_pairs` (integer, default 3) and `prompt_budget_hard` (integer thousands, default 16)
- `python-config-mirror`: `MCMConfig` gains two new fields for the prompt compaction settings

## Impact

- **Python (`dialogue/conversation.py`)**: `handle_event()` always trims dialogue tail to N pairs, then checks hard limit for potential context block rebuild.
- **Python (`llm/pruning.py`)**: Replaced — the old `prune_conversation()` becomes the new `compact_prompt()`.
- **Python (`dialogue/context_block.py`)**: Gains `rebuild_for_candidates(candidate_ids)` method.
- **Python (`models/config.py`)**: `MCMConfig` adds `prompt_dialogue_pairs` and `prompt_budget_hard` fields.
- **Lua (`talker_mcm.script`)**: Two new inputs in General Configuration section.
- **Lua (`interface/config.lua`)**: Two new config getters with defaults.
- **Tests**: New unit tests for the compactor, updated e2e scenarios, pruning.py tests replaced.
- **No wire protocol changes**: Purely prompt-side logic + MCM settings.
