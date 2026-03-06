## Why

The current `ConversationManager` rebuilds the system prompt (including dynamic world context like weather, time-of-day, and notable inhabitants) on every `handle_event()` call, destroying the LLM provider's prefix cache on every turn. The `deduplicated-prompt-architecture` change moves events, backgrounds, and memories to individual `[system]` messages — but many providers (Ollama, some Gemini models) reject or mangle multiple system messages. Both problems waste tokens and money: OpenAI's automatic prompt caching gives 50% discount on cached prefix tokens, but only when the serialized token prefix is byte-identical and ≥1024 tokens.

## What Changes

- **Static-only system prompt**: The single `[system]` message contains only timeless dialogue rules (~150 tokens). Weather, time-of-day, location, and notable inhabitants are removed from it.
- **Context block as `[user]` message**: A single append-only `[user]` message holds all backgrounds and memories, rendered as Markdown with structured tags. A synthetic `[assistant] "Ready."` follows it to establish clean turn alternation.
- **Weather/time/location in event instruction**: Volatile world state becomes part of the per-turn user instruction message (Layer 4), not the stable context prefix.
- **ContextBlock data model + Markdown renderer**: Internal `ContextBlock` class stores items as typed Python objects for O(1) dedup, with a `render_markdown()` method that iterates items in insertion order for cache-stable output.
- **Event filtering per step**: The picker step receives zero witness events (only the triggering event description). The dialogue step receives only events where the chosen speaker is a witness.
- **Universal provider compatibility**: Only one `[system]` message ever exists. All factual context uses `[user]` role. User/assistant alternation is maintained. No provider-specific branching needed.

## Capabilities

### New Capabilities
- `context-block-builder`: Append-only data model + Markdown renderer for backgrounds and memories, with set-based dedup tracking and `render_markdown()` for cache-stable LLM wire format
- `cache-friendly-message-layout`: Four-layer message assembly (static system → context user → Ready ack → dialogue turns) that maximizes prefix cache hits across LLM calls

### Modified Capabilities
- `two-step-dialogue-flow`: System prompt becomes static rules only; picker and dialogue user messages include per-turn weather/time/location; event filtering is step-specific (picker: no witness events; dialogue: speaker-witnessed events only)
- `system-message-injection`: Replaced by context block user message — backgrounds and memories are Markdown sections in a single `[user]` message instead of individual `[system]` messages
- `prompt-deduplication-tracker`: Replaced by `ContextBlock`'s internal set-based tracking; the separate `DeduplicationTracker` class is no longer needed as a standalone component
- `memory-diff-injection`: Diff logic moves into `ContextBlock.add_memory()` — per-character tracking via internal `_mem_keys` set instead of separate tracker
- `witness-event-injection`: Storage side unchanged; prompt injection changes — events are no longer global system messages but filtered per-step in the dialogue user message
- `python-world-context`: Dynamic world state (weather, time, location, inhabitants) removed from system prompt assembly; inhabitants data is still queried but goes into the context block; weather/time goes into event instruction

## Impact

- **Python (`dialogue/conversation.py`)**: Major refactor — `_build_system_prompt()` becomes static, `_messages` list structure changes to 4-layer layout, new `ContextBlock` dependency, event filtering logic in picker and dialogue steps
- **Python (`dialogue/dedup_tracker.py`)**: Replaced by `ContextBlock` or significantly simplified
- **Python (`prompts/`)**: `build_dialogue_user_message()` and picker message builders gain weather/time/location parameters; world context builders no longer feed into system prompt
- **Python (`prompts/world_context.py`)**: `build_world_context()` output no longer embedded in system prompt; inhabitants context may move into context block
- **Python (new `dialogue/context_block.py`)**: New module with `ContextBlock` class, `ContextItem` dataclass, `render_markdown()`
- **Tests**: Significant updates across conversation manager tests, prompt builder tests, and e2e scenarios to reflect new message structure
- **No Lua changes**: This is purely a Python-side prompt layout change
