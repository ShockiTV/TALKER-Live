## Why

The `ConversationManager` is fully scaffolded and wired end-to-end (event → handler → LLM → dialogue.display), but the actual tool-calling loop is stubbed. The `LLMClient.complete()` protocol returns `str` only — it has no `tools` parameter, cannot return tool calls, and the ConversationManager cannot execute tool calls against `get_memories` or `background`. Until this is fixed, dialogue generation falls back to a single LLM call with pre-fetched context injected into system messages, losing the ability for the LLM to dynamically query memories, read/write backgrounds, or make informed speaker choices.

## What Changes

- Extend the `LLMClient` protocol and `BaseLLMClient` abstract class with a new `complete_with_tools()` method that accepts tool definitions and returns structured responses (text OR tool calls)
- Add `ToolCall`, `ToolResult`, and `LLMToolResponse` models to `llm/models.py`
- Implement `complete_with_tools()` for OpenAI, OpenRouter, Ollama, and Proxy LLM clients
- Wire the ConversationManager's tool loop: dispatch tool calls → execute handlers → append results → re-call LLM until text response
- Add the `background` write/update tool schema (read-only `get_background` schema exists; full `background` tool with read/write/update actions replaces it)
- Add tool result formatting (memory tiers → human-readable text, background → structured display)

## Capabilities

### New Capabilities
- `llm-tool-calling`: LLM client infrastructure for tool/function calling across all providers (tool definitions, structured responses, tool call parsing)

### Modified Capabilities
- `tool-based-dialogue`: The existing spec requires "LLM client must support tool calling" (last requirement). This change implements that requirement and wires the tool loop, which is currently stubbed with a NOTE comment in conversation.py.

## Impact

- **LLM clients** (`llm/base.py`, `llm/models.py`, `llm/openai_client.py`, `llm/openrouter_client.py`, `llm/ollama_client.py`, `llm/proxy_client.py`): New method + response model on every provider
- **ConversationManager** (`dialogue/conversation.py`): Tool loop goes from stub to real implementation
- **Tool schemas** in `conversation.py`: `GET_BACKGROUND_TOOL` replaced by full `BACKGROUND_TOOL` with read/write/update actions
- **Existing tests**: Tests mocking `complete()` remain valid; new tests added for `complete_with_tools()`
- **No wire protocol changes**: All WS topics, payloads, and Lua code remain unchanged
- **No breaking changes**: `complete()` remains for non-tool calls; `complete_with_tools()` is additive
