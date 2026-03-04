## Why

Current dialogue system creates fresh message history for every event, wasting context and causing redundant tool calls. When evaluating 5 candidate speakers, the LLM calls `get_memories()` 5 times separately (5 tool executions). Over long play sessions, message history accumulates unchecked, eventually hitting context window limits. This change enables long-running conversations with efficient tool usage and predictable memory footprint.

## What Changes

- Add persistent conversation history in OpenAI client (single shared conversation across all events; LLM switches NPC "hats" via system prompt)
- Implement hybrid message pruning strategy (removes old tool results + old dialogue when context hits 75% of window; always preserves system + last 5 turns + last 5 tool results)
- Extend `background` tool to accept `character_ids: list[str]` for batch queries (up to 10 NPCs per call; returns `dict[char_id, background]`)
- Extend `get_character_info` tool to accept `character_ids: list[str]` for batch queries (same pattern as background)
- Restrict `get_memories` tool to single speaker only (not for candidate evaluation; enforced via system prompt + schema; `tiers` parameter optional, defaults to all tiers)
- Update system prompt with tool usage workflow (use backgrounds for speaker selection, fetch memories only after choosing speaker)

## Capabilities

### New Capabilities
- `openai-persistent-conversation`: Per-tenant (WebSocket session) OpenAI client with isolated conversation history; LLM changes character context via system prompt; full session isolation for multi-tenant deployments
- `context-aware-message-pruning`: Automatic pruning at 75% of context window; priority-based removal (old tools first, then old dialogue); guarantees preservation of system prompt + recent context
- `multi-npc-tool-batching`: `background` and `get_character_info` tools accept arrays of character IDs; return dict results; max 10 NPCs per batch
- `speaker-restricted-memory-queries`: `get_memories` restricted to single character (chosen speaker); system prompt instructs LLM workflow (backgrounds for selection, memories for chosen speaker only)

### Modified Capabilities
<!-- No existing capabilities are being modified -->

## Impact

**Affected Python Code:**
- `talker_service/src/talker_service/transport/session.py` — Add `llm_client` field for per-session client instances
- `talker_service/src/talker_service/llm/openai_client.py` — Add `_conversation: list[Message]` field; persist history across calls
- `talker_service/src/talker_service/dialogue/conversation.py` — Retrieve client from session context; tool schemas updated (batch parameters); handlers support multi-NPC queries; pruning logic added; system prompt includes tool usage rules
- `talker_service/src/talker_service/__main__.py` — Remove singleton client, add factory for per-session LLM clients
- `talker_service/src/talker_service/handlers/events.py` — Pass `session_id` to ConversationManager

**Wire Protocol:**
- No changes to Lua↔Python communication (all changes internal to Python service)

**User-Facing:**
- Reduced API costs (fewer tool calls, better context management)
- Improved dialogue coherence (LLM remembers cross-NPC interactions)
- More efficient speaker selection (batch background fetches)

**Deployment:**
- OpenAI-only initially (other providers can adopt pattern later)
- Backward compatible (existing single-char tool calls still work via array unpacking)
- No MCM changes required
