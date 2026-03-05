## Implementation Approach

This change implements four capabilities to optimize OpenAI conversation management and tool usage efficiency.

### 1. OpenAI Persistent Conversation

**Core Idea**: Each WebSocket session (game tenant) gets its own OpenAI client instance with isolated `_conversation: list[Message]` field. LLM switches NPC context via system prompt updates within that session.

**Implementation**:
- Store per-session LLMClient in `SessionContext` (new field: `llm_client: LLMClient | None`)
- On session creation, instantiate `OpenAIClient()` with empty `_conversation`
- Add `_conversation` field to `OpenAIClient.__init__()`
- Modify `complete_with_tools()` to append messages to `_conversation` instead of replacing
- Each event adds: system prompt (with NPC context) + event user message + tool calls + tool results + final response
- System prompt changes per event: "You are now speaking as [NPC name], [faction], [personality]"
- `ConversationManager.handle_event()` retrieves `llm_client` from session context instead of using singleton

**Benefits**:
- **Tenant isolation**: Each game instance maintains separate conversation history
- LLM builds cross-NPC understanding within that game world (e.g., "Duty and Freedom tensions affect this playthrough")
- No per-NPC session tracking overhead (single conversation per tenant, not per character)
- Clean separation: reconnect resumes same conversation, new session starts fresh

**Session Lifecycle**:
- **Session creation**: Instantiate new `OpenAIClient()` with empty `_conversation`
- **During session**: `_conversation` grows, pruning triggers at 75% threshold
- **Disconnect**: Session persists for reconnect (conversation retained)
- **Session cleanup** (optional): Clear old sessions after N hours idle

### 2. Context-Aware Message Pruning

**Core Idea**: Monitor token count; when hitting 75% of 128k window (96k tokens), prune to 50% (64k tokens) using priority-based strategy.

**Pruning Priority** (keep → remove):
1. System prompts (always keep)
2. Last 5 user/assistant dialogue pairs (~10 messages)
3. Last 5 tool result messages
4. Older dialogue messages (fill remaining budget, oldest-first)
5. Older tool results (removed first when over budget)

**Token Estimation**:
- Use rough heuristic: 1 token ≈ 4 characters
- Count all message.content + JSON.stringify(tool_calls)
- Optional: Integrate `tiktoken` for accuracy

**Implementation**:
```python
class ConversationManager:
    CONTEXT_WINDOW = 128_000
    PRUNING_THRESHOLD_PCT = 0.75  # Prune at 96k
    PRUNE_TARGET_PCT = 0.50       # Prune to 64k
    
    async def _prune_messages_hybrid(self, messages: list[Message]) -> list[Message]:
        # 1. Separate by type (system, dialogue, tools)
        # 2. Keep: all system + last 10 dialogue + last 5 tools
        # 3. Calculate remaining budget
        # 4. Fill budget with older messages (dialogue priority)
        # 5. Return pruned list
```

**Trigger**: Before each `complete_with_tools()` call in `handle_event()`

**Logging**: "Pruned {before}→{after} tokens (removed {N} tools, {M} dialogue)"

### 3. Multi-NPC Tool Batching

**Core Idea**: `background` and `get_character_info` tools accept `character_ids: list[str]`, return `dict[char_id, result]`.

**Tool Schema Updates**:
```python
BACKGROUND_TOOL = {
    "parameters": {
        "character_ids": {  # Was: "character_id" (singular string)
            "type": "array",
            "items": {"type": "string"},
            "description": "Character IDs (max 10 per call)"
        },
        "action": {"type": "string", "enum": ["read", "write", "update"]},
        # ... content/field/value for write/update ...
    },
    "required": ["character_ids", "action"]
}

GET_CHARACTER_INFO_TOOL = {
    "parameters": {
        "character_ids": {  # Same pattern
            "type": "array",
            "items": {"type": "string"},
            "description": "Character IDs (max 10 per call)"
        }
    },
    "required": ["character_ids"]
}
```

**Handler Implementation** (`_handle_background`):
```python
async def _handle_background(
    self,
    character_ids: list[str] | str,  # Accept both for backward compat
    action: str = "read",
    ...
) -> dict[str, Any]:
    # Normalize to list
    if isinstance(character_ids, str):
        character_ids = [character_ids]
    
    if action == "read":
        # Build BatchQuery with one sub-query per char
        batch = BatchQuery()
        for char_id in character_ids:
            batch.add(f"bg_{char_id}", "memory.background", params={"character_id": char_id})
        
        result = await self.state_client.execute_batch(batch, timeout=10.0)
        
        # Return dict[char_id, background]
        return {char_id: result[f"bg_{char_id}"] or {} for char_id in character_ids}
    
    elif action in ["write", "update"]:
        # Single-character only
        if len(character_ids) != 1:
            return {"error": "write/update only supports single character"}
        # ... existing logic ...
```

**Backward Compat**: Handler accepts both `str` and `list[str]`, normalizes to list internally.

**Batch Limit**: Enforce max 10 NPCs per call (return error if exceeded).

### 4. Speaker-Restricted Memory Queries

**Core Idea**: LLM uses backgrounds for speaker selection, memories only for chosen speaker. Enforced via schema + system prompt.

**Tool Schema Update**:
```python
GET_MEMORIES_TOOL = {
    "function": {
        "name": "get_memories",
        "description": "Retrieve memories for THE CHOSEN SPEAKER ONLY. Do NOT use for candidate evaluation—use backgrounds instead.",
        "parameters": {
            "character_id": {  # SINGULAR (not array)
                "type": "string",
                "description": "The character ID of the speaker you've chosen"
            },
            "tiers": {  # OPTIONAL
                "type": "array",
                "items": {"type": "string", "enum": ["events", "summaries", "digests", "cores"]},
                "description": "Which tiers to retrieve. Omit to fetch all tiers."
            }
        },
        "required": ["character_id"]  # tiers NOT required
    }
}
```

**Handler Update**:
```python
async def _handle_get_memories(
    self,
    character_id: str,  # Singular only
    tiers: list[str] | None = None,  # Optional
) -> dict[str, Any]:
    if tiers is None:
        tiers = ["events", "summaries", "digests", "cores"]  # All tiers
    
    # ... existing batch query logic ...
```

**System Prompt Addition**:
```text
**Tool Usage Rules:**
1. **background(character_ids)**: Use this to evaluate ALL candidates before choosing a speaker
   - You can fetch backgrounds for multiple characters at once
   - Example: background(character_ids=["0", "npc_123", "npc_456"])
   
2. **get_memories(character_id, tiers)**: ONLY use AFTER choosing the speaker
   - You can ONLY fetch memories for the character you've decided will speak
   - Do NOT fetch memories for candidates you're evaluating
   - Memories are expensive; use backgrounds for speaker selection
   
3. **Workflow:**
   a. Read event context + candidate list
   b. Fetch backgrounds for candidates (if needed) via background(character_ids=[...])
   c. Choose speaker based on faction, personality, background
   d. Fetch memories ONLY for chosen speaker via get_memories(character_id=...)
   e. Generate dialogue for that speaker
```

**Enforcement**: LLM learns workflow via system prompt; schema prevents multi-char memory queries.

## File Changes

### Modified Files

**`talker_service/src/talker_service/llm/openai_client.py`**:
- Add `self._conversation: list[Message] = []` in `__init__()`
- Modify `complete_with_tools()`: append to `_conversation` instead of creating fresh list
- Add `reset_conversation()` method for manual resets (called on WS reconnect)

**`talker_service/src/talker_service/dialogue/conversation.py`**:
- Update `GET_MEMORIES_TOOL` schema (singular `character_id`, optional `tiers`)
- Update `BACKGROUND_TOOL` schema (`character_ids: list[str]`)
- Update `GET_CHARACTER_INFO_TOOL` schema (`character_ids: list[str]`)
- Modify `_handle_background()`: accept list, build BatchQuery, return dict
- Modify `_handle_get_character_info()`: accept list, build BatchQuery, return dict
- Modify `_handle_get_memories()`: make `tiers` optional (default all)
- Add `_prune_messages_hybrid()` method
- Update `_build_system_prompt()`: add tool usage rules section
- Call `_prune_messages_hybrid()` before each LLM call in `handle_event()`

**`talker_service/src/talker_service/llm/models.py`** (if needed):
- Add token counting utilities (or keep as private helpers in `conversation.py`)

### New Files

None (all changes are modifications to existing files).

## Testing Strategy

### Unit Tests

**`tests/test_openai_client.py`**:
- Test `_conversation` persistence across multiple `complete_with_tools()` calls
- Test `reset_conversation()` clears history
- Mock `httpx.AsyncClient` to verify request bodies include full history

**`tests/test_conversation_manager.py`**:
- Test `_prune_messages_hybrid()` with various message counts
- Verify pruning preserves system + recent context
- Test batch tool handlers return correct dict format
- Test single-char tool calls still work (backward compat)

### Integration Tests

**`tests/integration/test_tool_batching.py`**:
- Call `background(character_ids=["1", "2", "3"])` via `ConversationManager`
- Verify single `state.query.batch` roundtrip
- Verify dict response format

**`tests/e2e/test_persistent_conversation.py`**:
- Simulate 3 sequential events with same `ConversationManager`
- Verify `_conversation` grows (not reset)
- Verify pruning triggers at threshold

### Manual Testing

- Start game, trigger 20+ dialogue events
- Monitor `talker_service.log` for pruning messages
- Verify dialogue coherence across NPCs (mentions past events)
- Check OpenAI API usage (reduced calls vs. baseline)

## Rollout Plan

### Phase 1: Core Implementation
1. Add `_conversation` field to OpenAI client
2. Implement pruning logic in `ConversationManager`
3. Unit tests for both

### Phase 2: Tool Batching
1. Update tool schemas (backward-compatible)
2. Modify handlers (accept list, return dict)
3. Integration tests for batch queries

### Phase 3: System Prompt + Validation
1. Add tool usage rules to system prompt
2. E2E tests with real LLM calls (optional extra, gated by env var)
3. Manual testing in-game

### Phase 4: Monitoring & Tuning
1. Log pruning frequency and token counts
2. Collect metrics: tool calls per event, context window usage
3. Tune thresholds if needed (75% pruning trigger, 50% target)

### Rollback Plan

If conversation persistence causes issues:
- Add MCM toggle: "Enable Persistent Conversation" (default: true)
- When disabled, `complete_with_tools()` resets `_conversation` each call
- No code removal needed; just conditional behavior

## Open Questions

1. **Pruning threshold**: Is 75% → 50% the right range, or should it be more aggressive (e.g., 70% → 40%)?
2. **Token counting**: Use simple heuristic (4 chars/token) or integrate `tiktoken`?
3. **Conversation reset**: Should there be a manual reset command (e.g., player console command), or is game-load-only sufficient?
4. **Batch size limit**: Is 10 NPCs per batch reasonable, or should it be higher/lower?
5. **get_character_info batching**: Should this tool also support batch queries, or is single-char sufficient? (Proposal includes it, but can be deferred)
