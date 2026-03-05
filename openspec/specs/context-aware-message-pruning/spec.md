# Context-Aware Message Pruning

## Overview

Automatic pruning of message history when conversation approaches context window limit. Monitors token count before each LLM call; when hitting 75% of 128k token window (96k tokens), prunes to 50% (64k tokens) using priority-based strategy that preserves system prompts and recent context while removing older tool results and dialogue.

## Requirements

### MUST

- **M1**: Pruning MUST trigger when estimated token count ≥ 75% of context window (96k tokens for gpt-4o/gpt-4o-mini)
- **M2**: Pruning MUST reduce token count to ≤ 50% of context window (64k tokens)
- **M3**: Pruning MUST preserve ALL system prompt messages (never removed)
- **M4**: Pruning MUST preserve the last 5 user/assistant dialogue pairs (~10 messages minimum)
- **M5**: Pruning MUST preserve the last 5 tool result messages (most recent tool calls)
- **M6**: Pruning MUST remove old messages in priority order: old tool results removed before old dialogue
- **M7**: Pruning MUST execute before each `complete_with_tools()` call in `ConversationManager.handle_event()`
- **M8**: Pruning MUST log summary at INFO level: "Pruned {before}→{after} tokens (removed {N} tools, {M} dialogue)"

### SHOULD

- **S1**: Token estimation SHOULD use a heuristic of ~4 characters per token (simple, fast)
- **S2**: Implementation SHOULD count tokens for: `message.content` + `JSON.stringify(message.tool_calls)` for all messages
- **S3**: After preserving guaranteed messages, remaining budget SHOULD be filled with older messages (dialogue prioritized over tools)

### MAY

- **M1**: Implementation MAY integrate `tiktoken` library for accurate token counting (alternative to heuristic)
- **M2**: Implementation MAY make thresholds configurable via environment variables (PRUNING_THRESHOLD_PCT, PRUNE_TARGET_PCT)

## Non-Requirements

- ❌ Per-message importance scoring (simple time-based pruning only)
- ❌ Semantic analysis of tool results (no "unreferenced tool result" detection)
- ❌ Differential pruning strategies per provider (OpenAI-specific for now)

## Validation

### Unit Test Scenarios

1. **Below threshold**: 50k tokens → no pruning, message list unchanged
2. **At threshold**: 96k tokens → prunes to ~64k tokens
3. **Preservation guarantees**: After pruning, verify: all system prompts present, last 5 dialogue pairs present, last 5 tool results present
4. **Priority order**: 150k tokens (over limit) → removes old tools before old dialogue

### Integration Test Scenarios

1. **Long conversation flow**: Simulate 30 sequential events → verify pruning triggers multiple times, conversation size stabilizes

### Acceptance Criteria

- After 50 dialogue events, conversation size remains under 70k tokens (pruned multiple times)
- System prompts always present (all 50 system messages retained if each is small enough)
- Recent context intact (last 5 user/assistant pairs always present)

## Edge Cases

1. **Recent messages exceed target**: If last 5 dialogue + last 5 tools > 64k tokens, keep only recent messages (acceptable degradation)
2. **Huge tool results**: Single tool result > 10k tokens → still counted, may cause frequent pruning (acceptable; LLM context aware)
3. **Empty conversation**: Token count = 0 → no pruning triggered

## Dependencies

- `openai-persistent-conversation`: Provides the conversation history to prune

## Related Specs

- `openai-persistent-conversation`: Conversation accumulates over time
- This spec ensures accumulation doesn't exceed limits

## Metrics

- **Pruning frequency**: Log count of pruning events per game session
- **Token savings**: Log tokens removed per pruning event
- **Conversation size**: Track average conversation size after each event
