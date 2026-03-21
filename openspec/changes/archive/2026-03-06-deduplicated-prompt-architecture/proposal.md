## Why

The current conversation manager inlines event descriptions and character backgrounds into every user message. When multiple characters witness the same events, those events are duplicated across memory dumps — 5 witnesses × 10 events = 50 event descriptions consuming tokens. Backgrounds are re-sent in full for the picker step and again implicitly through memory context. This wastes context window budget and makes the LLM's timeline harder to reason about.

## What Changes

- **Events as shared system messages**: Game events are injected as `[system]` messages with witness lists (name + ID). Deduplicated globally across the entire message array by unique timestamp.
- **Backgrounds as shared system messages**: Character backgrounds are injected as `[system]` messages, deduplicated by character ID across the message array.
- **Memories (summaries/digests/cores) as shared system messages**: Character-scoped narrative memories are injected as `[system]` messages, deduplicated by `(character_id, start_ts)`.
- **Pointer-based picker and dialogue messages**: The picker `[user]` message becomes just an event timestamp + candidate ID list. The dialogue `[user]` message becomes just a character ID + event timestamp reference. All heavy context is already in system messages.
- **Global unique timestamps in Lua**: Replace per-character `seq` counter with a global monotonic `unique_ts()` function (bumps collisions so `game_time_ms` is always unique). Used as the single identity/dedup key for events and memory items.
- **Background generation uses fast model**: `BackgroundGenerator` accepts a `fast_llm_client` instead of the main model.
- **DeduplicationTracker**: New class replaces `_memory_timestamps` dict, tracking injected event timestamps, background IDs, and memory item IDs. Includes `rebuild_from_messages()` for consistency after pruning.

## Capabilities

### New Capabilities
- `global-unique-timestamp`: Lua-side global monotonic timestamp generator replacing per-character seq counters
- `prompt-deduplication-tracker`: Python-side dedup tracker for events, backgrounds, and memories across the message array
- `system-message-injection`: Formatting and injection of events, backgrounds, and memories as deduplicated system messages
- `pointer-based-dialogue-messages`: Lightweight picker and dialogue user messages that reference system-message content by ID/timestamp

### Modified Capabilities
- `background-generation-thread`: Background generation uses fast_llm_client; backgrounds injected as system messages rather than inline in picker
- `two-step-dialogue-flow`: Picker and dialogue user messages become pointer-based; events/backgrounds/memories moved to system messages
- `memory-diff-injection`: Replaced by deduplication tracker; diff logic now operates at system-message level across all content types
- `witness-event-injection`: Witness list now included in event system messages; per-character fan-out storage unchanged but prompt injection deduplicated
- `four-tier-memory-store`: Per-character seq replaced by global unique_ts; all tiers use unique_ts as identity key

## Impact

- **Lua**: `memory_store_v2.lua` — replace `assign_seq` with `unique_ts()`. `Event.create()` — use `unique_ts()` instead of raw `engine.get_game_time_ms()`. `interface/trigger.lua` — timestamp assignment change.
- **Python (conversation.py)**: Major refactor of `ConversationManager` — new dedup tracker, system message injection loop, pointer-based picker/dialogue messages, removal of `_memory_timestamps` and inline memory formatting.
- **Python (prompts/)**: New formatters for event/background/memory system messages. `build_dialogue_user_message` and `build_candidates_message` become pointer-based.
- **Python (background_generator.py)**: Accept `fast_llm_client` parameter.
- **Python (compaction.py)**: Compacted items use `start_ts` as primary key (already works with delete-then-append pattern).
- **Tests**: Significant test updates across Lua (memory_store_v2, trigger) and Python (conversation, prompts, e2e scenarios).
