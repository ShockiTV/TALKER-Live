# OpenAI Persistent Conversation

## Overview

Each WebSocket session (game tenant) gets its own OpenAI client instance with isolated `_conversation: list[Message]` state. The client is stored in `SessionContext` and accumulates messages across multiple events within that session. This enables long-form multi-turn conversations where the LLM builds context over time, with full tenant isolation. The LLM switches character context via system prompts ("You are now speaking as...") rather than maintaining separate per-NPC sessions.

## Requirements

### MUST

- **M1**: `SessionContext` MUST add `llm_client: LLMClient | None` field (defaults to `None`)
- **M2**: `OpenAIClient` MUST add `_conversation: list[Message]` field initialized to empty list in `__init__`
- **M3**: `complete_with_tools()` MUST append new messages to `_conversation` (not replace)
- **M4**: API calls MUST send full `_conversation` list to OpenAI
- **M5**: Successful responses MUST append assistant message to `_conversation`
- **M6**: Client MUST provide `reset_conversation()` method to clear history
- **M7**: `ConversationManager` MUST retrieve `llm_client` from session context (not use singleton)
- **M8**: If session's `llm_client` is `None`, MUST instantiate new `OpenAIClient()` via factory method

### SHOULD

- **S1**: `complete()` method (non-tool variant) SHOULD also use `_conversation` if implemented
- **S2**: Client SHOULD provide `get_conversation()` method for debugging/testing
- **S3**: Conversation state SHOULD survive across multiple `handle_event()` calls within same session
- **S4**: Session cleanup logic SHOULD optionally clear old sessions after configurable idle timeout
- **S5**: Factory method SHOULD respect current MCM config when instantiating per-session clients

### MAY

- **M1**: Implementation MAY add an MCM toggle for persistent conversation (default: enabled)
- **M2**: Implementation MAY expose conversation history via debug endpoint for diagnostics

## Non-Requirements

- ❌ Per-NPC conversation tracking (explicitly avoided; one shared conversation only)
- ❌ Conversation persistence to disk (ephemeral; clears on service restart)
- ❌ Conversation branching or checkpointing

## Validation

### Unit Test Scenarios

1. **Session isolation**: Create 2 sessions, verify each has independent `_conversation` state
2. **Conversation persistence**: Call `complete_with_tools()` twice in same session, verify `_conversation` contains both exchanges
3. **Message ordering**: Verify messages appear in chronological order: user → assistant → tool_call → tool_result → user → ...
4. **Reset**: Populate conversation, call `reset_conversation()`, verify empty list
5. **Lazy initialization**: Access session without `llm_client`, verify factory creates new instance

### Integration Test Scenarios

1. **Multi-event conversation**: Handle 5 events in session A, verify context builds (LLM references earlier events)
2. **Cross-session isolation**: Handle events in session A and session B, verify no cross-contamination
3. **Tool usage accumulation**: Event 1 calls tool A, Event 2 calls tool B, verify both in same session's conversation history
4. **Reconnection**: Disconnect session A, reconnect with same token, verify conversation resumes

### Acceptance Criteria

- After 10 dialogue events in session A, `_conversation` contains ~50-100 messages specific to that session
- Session B running concurrently has separate conversation history
- LLM responses reference past events within same session ("As I mentioned when the mutant attacked...")
- New sessions start with empty conversation

## Edge Cases

1. **Empty conversation**: First call with no history → works normally
2. **API error mid-conversation**: Failed call should NOT corrupt `_conversation` state
3. **Manual reset during event**: Calling `reset_conversation()` during event handling clears history but doesn't break current call
4. **Session without client**: Event handler checks session, finds `llm_client=None`, creates new client on-demand
5. **Multiple sessions**: Service handles 10+ concurrent sessions, each with independent conversation state
6. **Massive conversation growth**: Handled by `context-aware-message-pruning` spec (separate capability)
7. **WebSocket disconnect mid-event**: Session persists; next event after reconnect continues same conversation
8. **Service restart**: All sessions lost (acceptable; ephemeral by design)

## Dependencies

- None (foundational capability)

## Related Specs

- `context-aware-message-pruning`: Manages conversation size via automatic pruning
