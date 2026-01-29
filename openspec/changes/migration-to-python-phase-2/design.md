## Context

Phase 1 established unidirectional ZMQ communication (Lua PUB → Python SUB) for event publishing and config sync. The Python service currently logs events but performs no AI processing. All dialogue generation still runs in Lua via `bin/lua/infra/AI/` modules that make HTTP calls to LLM APIs.

Current dialogue flow:
```
Trigger → talker.register_event() → AI_request.generate_dialogue() 
       → pick_speaker() → update_narrative() → request_dialogue()
       → prompt_builder → GPT/OpenRouter/Ollama → display_dialogue()
```

Phase 2 target architecture:
```
Trigger → talker.register_event() → Python (via ZMQ)
       → DialogueGenerator.generate()
       → pick_speaker() → query Lua for witnesses/context
       → update_narrative() → query Lua for memories → compress if needed → LLM call
       → request_dialogue() → build prompt → LLM call
       → send display command → Lua displays dialogue
```

Key constraint: Lua must remain the source of truth for game state (event_store, memory_store, character data) because save/load is handled by STALKER's persistence system.

## Goals / Non-Goals

**Goals:**
- Move all LLM API calls to Python (GPT, OpenRouter, Ollama, proxy)
- Move prompt building logic to Python
- Move speaker selection and memory compression orchestration to Python
- Establish bidirectional ZMQ communication (Python → Lua commands)
- Enable Python to query Lua for state (memories, events, characters)
- Remove Lua AI modules completely (no fallback mode)

**Non-Goals:**
- Moving state persistence to Python (stays in Lua)
- Hot-swapping between Lua/Python AI (Python-only)
- Local LLM inference in Python (use existing Ollama/proxy pattern)
- Changing the event/memory data model
- Performance optimization of prompt building

## Decisions

### D1: Bidirectional ZMQ Pattern

**Decision:** Add second PUB/SUB pair (Python PUB → Lua SUB) on separate port

```
Port 5555: Lua PUB  → Python SUB (events, config - existing)
Port 5556: Python PUB → Lua SUB (commands, query responses - new)
```

**Alternatives Considered:**
- Single REQ/REP socket: Blocks game loop waiting for response
- ROUTER/DEALER: More complex, overkill for this use case
- Reuse port 5555 with topics: ZMQ doesn't support mixed PUB/SUB on same socket

**Rationale:** Keeps the fire-and-forget pattern that works well in Phase 1. Lua can process commands asynchronously via game loop polling. Separate port avoids complexity.

### D2: Request-Response Correlation

**Decision:** Use correlation IDs for state queries (request_id in payload)

```
Lua → Python: game.event {..., triggers_dialogue: true, request_id: "abc123"}
Python → Lua: state.query {type: "memories", character_id: "123", request_id: "abc123"}
Lua → Python: state.response {request_id: "abc123", data: [...]}
Python → Lua: dialogue.display {speaker_id: "123", text: "...", request_id: "abc123"}
```

**Alternatives Considered:**
- Synchronous REQ/REP: Blocks game loop
- Implicit ordering: Fragile if messages reorder
- Callback registry: Complex state management in Lua

**Rationale:** Correlation IDs allow Python to track multiple in-flight requests. Lua can respond to queries out of order. Matches async patterns in both languages.

### D3: State Query Protocol

**Decision:** Python sends typed query requests, Lua responds with serialized state

Query types:
- `memories.get`: Fetch memory context for a character
- `events.recent`: Fetch recent events (last N or since timestamp)
- `character.get`: Fetch character data by ID
- `characters.nearby`: Fetch characters near a position

**Alternatives Considered:**
- Push all state to Python on every event: High bandwidth, stale data
- Python maintains shadow state: Sync complexity, drift risk
- Lazy caching in Python: Still need query mechanism

**Rationale:** Query-on-demand minimizes data transfer. Lua remains authoritative. Python requests only what it needs for the current dialogue generation.

### D4: LLM Client Architecture

**Decision:** Abstract LLM interface with provider implementations

```python
class LLMClient(Protocol):
    async def complete(self, messages: list[Message], opts: LLMOptions) -> str: ...

class OpenAIClient(LLMClient): ...
class OpenRouterClient(LLMClient): ...
class OllamaClient(LLMClient): ...
class ProxyClient(LLMClient): ...
```

**Alternatives Considered:**
- Single client with provider switch: Less flexible, harder to test
- LangChain/LiteLLM: Heavy dependencies, less control
- Direct HTTP in each function: Code duplication

**Rationale:** Clean abstraction allows easy testing with mocks. Each provider has specific quirks (auth, endpoints, response format) that benefit from isolation.

### D5: Prompt Builder Port Strategy

**Decision:** Direct port of `prompt_builder.lua` to Python, maintaining same prompt structure

**Alternatives Considered:**
- Redesign prompts from scratch: Risk regression in dialogue quality
- Use prompt templates (Jinja): Adds complexity, prompts are already string concatenation
- Keep prompts in Lua, Python just orchestrates: Defeats purpose of migration

**Rationale:** The current prompts have been tuned over time. Direct port preserves behavior. Python's string handling and f-strings make the code cleaner. Can iterate on prompts after migration is stable.

### D6: Dialogue Display Command

**Decision:** Python sends display command, Lua handles game API calls

```
Python → Lua: dialogue.display {
    speaker_id: "123",
    speaker_name: "Wolf", 
    text: "Get out of here, stalker!",
    request_id: "abc123"
}
```

Lua handler calls `game_adapter.display_dialogue()` and creates dialogue event.

**Alternatives Considered:**
- Python calls game API directly: Impossible, no game access
- Return dialogue in query response: Conflates query/command
- Lua polls for pending dialogue: Higher latency

**Rationale:** Clean separation. Python decides what to say, Lua handles how to display it. Lua can add game-specific logic (sound, animations) without Python changes.

### D7: Error Handling - Python Service Required

**Decision:** If Python service unavailable, dialogue generation fails silently (no fallback)

**Alternatives Considered:**
- Keep Lua fallback: Maintenance burden, two codepaths
- Queue requests until service available: Complex, stale context
- Show error to player: Disruptive to gameplay

**Rationale:** Users must run Python service for AI features. This is documented as a breaking change. Simplifies codebase by removing Lua AI modules entirely. Silent failure means game continues without AI dialogue (events still recorded).

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Latency from IPC round-trips | Dialogue feels slow | Async processing, batch queries where possible |
| Query response lost | Dialogue generation hangs | Timeout + retry, eventually fail silently |
| Python service crash mid-dialogue | Partial state corruption | Idempotent operations, request_id tracking |
| Prompt regression after port | Dialogue quality drops | Side-by-side testing before removing Lua |
| Breaking change disrupts users | Complaints, confusion | Clear documentation, prominent warnings |

## Migration Plan

### Deployment Steps (Incremental)

1. **Add Python LLM clients** - No game impact (not called yet)
2. **Add Python prompt builder** - No game impact (not called yet)
3. **Add Lua SUB socket + command handlers** - Listens but receives nothing
4. **Add Python PUB socket** - Can send commands
5. **Add state query handlers in Lua** - Responds to queries
6. **Add Python dialogue generator** - Orchestrates full flow
7. **Wire up: event triggers Python dialogue** - AI moves to Python
8. **Remove Lua AI modules** - Breaking change complete

### Rollback Strategy

Before step 7: No rollback needed, Lua AI still works.
After step 7: Restore Lua AI modules from git, remove ZMQ integration from talker.lua.

### Testing Strategy

- Unit tests for Python LLM clients (mock HTTP)
- Unit tests for Python prompt builder (compare output to Lua version)
- Integration test: Python queries Lua state via ZMQ
- Integration test: Full dialogue flow with mock LLM
- Manual test: Play game, verify dialogue quality matches pre-migration

## Open Questions

None - all resolved:

1. **Timeout values:** Add MCM entries for configurable timeouts. Defaults: LLM calls = 60 seconds, state queries = 30 seconds.
2. **Memory compression ownership:** Python triggers compression (owns thresholds like COMPRESSION_THRESHOLD), generates compressed text via LLM, then calls Lua to apply the update to memory_store. Lua remains state authority, Python is compute layer.
