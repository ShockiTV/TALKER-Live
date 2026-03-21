## Context

The `ConversationManager` in `dialogue/conversation.py` is fully wired end-to-end (event handler → LLM → dialogue.display), but the tool-calling loop is stubbed because `LLMClient.complete()` returns `str` only. It has no `tools` parameter, no way to parse tool calls from the response, and no model for structured tool call/result objects. The ConversationManager currently falls back to pre-fetching memories and injecting them into the system prompt, bypassing the dynamic tool loop the design doc envisions.

All four LLM providers (OpenAI, OpenRouter, Ollama, Proxy) use httpx and return `data["choices"][0]["message"]["content"]` (or Ollama's equivalent). The OpenAI-compatible API format for tool calling is well-standardized: `tools` array in the request body, `tool_calls` array in the response message, and `tool` role messages for results.

The existing `llm/models.py` has `Message`, `LLMOptions`, and an unused `LLMResponse` dataclass. The `Message.to_dict()` only returns `{role, content}` — no support for `tool_calls` or `tool_call_id` fields.

## Goals / Non-Goals

### Goals
- Add `complete_with_tools()` method to `LLMClient` protocol and `BaseLLMClient`
- Add `ToolDefinition`, `ToolCall`, `ToolResult`, and `LLMToolResponse` models
- Extend `Message` to carry tool-call and tool-result content
- Implement `complete_with_tools()` for all four providers (OpenAI, OpenRouter, Ollama, Proxy)
- Wire the ConversationManager's tool loop to use real `complete_with_tools()` calls
- Replace `GET_BACKGROUND_TOOL` with full `BACKGROUND_TOOL` (read/write/update actions)
- Maintain backward compatibility — `complete()` remains unchanged for non-tool callers

### Non-Goals
- Adding new tools beyond `get_memories` and `background` (deferred to later changes)
- Streaming tool call responses (all providers use non-streaming calls)
- Retry/fallback logic if tool calling fails (keep simple for v1)
- Multi-turn conversation history across events (each event is an independent turn)
- Changes to the Lua side or WS wire protocol

## Decisions

### D1: Separate method vs. extending `complete()`

**Decision**: Add a new `complete_with_tools()` method rather than adding optional `tools` param to `complete()`.

**Rationale**: The return type changes fundamentally — `complete()` returns `str`, but tool-calling returns `LLMToolResponse` (which may contain text OR tool calls). Adding an optional `tools` param to `complete()` would require all callers to handle both return types or require overloaded return types. A separate method keeps `complete() → str` clean for the existing dialogue generator, speaker selector, memory compressor, and all tests that mock it.

### D2: Response model shape

**Decision**: `LLMToolResponse` is a dataclass with `text: str | None` and `tool_calls: list[ToolCall]`. Exactly one is populated — if `tool_calls` is non-empty, `text` is None (and vice versa).

**Rationale**: This mirrors the OpenAI API behavior where `finish_reason="tool_calls"` means content is null, and `finish_reason="stop"` means content is the text. A union type (`str | list[ToolCall]`) was considered but is less ergonomic — callers prefer `response.text` vs `response.tool_calls` over `isinstance()` checks.

### D3: Message model extension

**Decision**: Add optional fields to `Message`: `tool_calls: list[ToolCall] | None`, `tool_call_id: str | None`, `name: str | None`. Add `Message.tool_result()` factory and extend `to_dict()` to include these fields when present.

**Rationale**: The OpenAI API requires assistant messages with `tool_calls`, and `tool` role messages with `tool_call_id` and content. We need `Message` to carry these for the multi-turn tool loop. Default values of `None` maintain backward compatibility — existing code constructing `Message(role, content)` is unaffected.

### D4: Tool definition format

**Decision**: Use OpenAI-compatible tool definition dicts (already used by `GET_MEMORIES_TOOL` and `GET_BACKGROUND_TOOL` in conversation.py). The `ToolDefinition` TypedDict provides type safety. Provider clients translate to provider-specific format if needed.

**Rationale**: The tool schemas in conversation.py already use OpenAI format. OpenRouter uses the same format. Ollama supports it via the `/api/chat` `tools` parameter. The Proxy client targets OpenAI-compatible endpoints. No translation needed for most providers.

### D5: Ollama tool calling support

**Decision**: Ollama's `/api/chat` supports `tools` directly (since Ollama 0.3+). Use the same OpenAI-compatible format. If a model doesn't support tools, the response simply won't contain `tool_calls` — the caller (ConversationManager) handles this gracefully by treating it as a direct text response.

**Rationale**: Modern Ollama versions support tool calling natively. No separate tool-calling strategy needed. Models without tool support just respond with text, which the tool loop already handles.

### D6: Tool call ID generation

**Decision**: For providers that don't return tool call IDs (unlikely with OpenAI format, but possible with Ollama or custom proxies), generate synthetic IDs using `f"call_{uuid4().hex[:8]}"`.

**Rationale**: The OpenAI protocol requires tool result messages to reference a `tool_call_id`. If a provider omits it, we need a synthetic one. UUIDs prevent collisions in multi-tool-call scenarios.

### D7: ConversationManager tool loop wiring

**Decision**: Replace the stub comment block in `handle_event()` with a real loop: call `complete_with_tools(messages, tools=TOOLS)`, check for tool calls, execute via `_execute_tool_call()`, append `Message.tool_result()`, repeat until text response or max iterations.

**Rationale**: The scaffolding (tool handlers, tool schemas, `_execute_tool_call()` dispatch) already exists. The loop just needs to call the new method and handle the `LLMToolResponse` type.

### D8: Background tool schema upgrade

**Decision**: Replace `GET_BACKGROUND_TOOL` (read-only) with `BACKGROUND_TOOL` that supports `action: read|write|update`. Add `_handle_background()` handler that dispatches read to state queries and write/update to state mutations.

**Rationale**: The design doc requires the LLM to write/update backgrounds (traits, backstory, connections) during dialogue generation. Read-only `get_background` is insufficient. The mutation path already exists in `state_client.mutate_batch()`.

## Risks / Trade-offs

### R1: Provider inconsistency
**Risk**: Not all models support tool calling equally. Some Ollama models may ignore tools entirely.
**Mitigation**: The tool loop has a max iteration limit and gracefully handles text-only responses. If the LLM never calls tools, the ConversationManager still works (behaves like current pre-fetch fallback, but with tool instructions in the prompt).

### R2: Increased latency
**Risk**: Each tool call iteration adds a round-trip: LLM call → tool execution (WS query to Lua) → LLM call.
**Mitigation**: Pre-fetch optimization remains (speaker's recent memories fetched before first LLM call). The max iteration limit (5) bounds worst-case latency. Most dialogue should complete in 1-2 tool calls.

### R3: Backward compatibility of `Message.to_dict()`
**Risk**: Adding optional fields to `Message` might affect serialization in unexpected places.
**Mitigation**: New fields default to `None` and `to_dict()` only includes them when set. All existing `Message(role="...", content="...")` call sites are unaffected.

### R4: Test surface expansion
**Risk**: Every LLM client now needs tool-calling tests in addition to `complete()` tests.
**Mitigation**: Factor out a shared `_build_tool_request_body()` helper in `BaseLLMClient` to reduce per-provider duplication. Use parameterized fixtures for tool-call response parsing tests.
