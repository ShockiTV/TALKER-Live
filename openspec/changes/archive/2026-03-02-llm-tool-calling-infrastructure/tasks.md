## 1. Models (`llm/models.py`)

- [x] 1.1 Add `ToolCall` dataclass with `id`, `name`, `arguments` fields
- [x] 1.2 Add `ToolResult` dataclass with `tool_call_id`, `name`, `content` fields
- [x] 1.3 Add `LLMToolResponse` dataclass with `text: str | None` and `tool_calls: list[ToolCall]`
- [x] 1.4 Extend `Message` with optional `tool_calls`, `tool_call_id`, `name` fields (default None)
- [x] 1.5 Add `Message.tool_result(tool_call_id, name, content)` factory classmethod
- [x] 1.6 Update `Message.to_dict()` to include tool fields when present (tool_calls serialized as OpenAI format, tool role includes tool_call_id and name)

## 2. Base Client (`llm/base.py`)

- [x] 2.1 Add `complete_with_tools(messages, tools, opts)` to `LLMClient` protocol returning `LLMToolResponse`
- [x] 2.2 Add abstract `complete_with_tools()` to `BaseLLMClient`
- [x] 2.3 Add `_parse_tool_calls(raw_tool_calls)` helper to `BaseLLMClient` that parses API tool call objects into `ToolCall` list (with synthetic ID generation for missing IDs)
- [x] 2.4 Add `_build_tool_response(data)` helper to `BaseLLMClient` that builds `LLMToolResponse` from raw API response dict (text vs tool_calls discrimination)

## 3. Provider Implementations

- [x] 3.1 Implement `OpenAIClient.complete_with_tools()` — add `tools` to request body, parse tool_calls from response, reuse retry logic
- [x] 3.2 Implement `OpenRouterClient.complete_with_tools()` — same OpenAI-compatible format, add tools to request body
- [x] 3.3 Implement `OllamaClient.complete_with_tools()` — add `tools` to `/api/chat` body, parse response with synthetic ID fallback
- [x] 3.4 Implement `ProxyClient.complete_with_tools()` — add `tools` to request body, handle both OpenAI format and text-only fallback

## 4. ConversationManager Tool Loop (`dialogue/conversation.py`)

- [x] 4.1 Replace `GET_BACKGROUND_TOOL` with `BACKGROUND_TOOL` schema (read/write/update actions)
- [x] 4.2 Add `_handle_background()` handler dispatching read/write/update to state client
- [x] 4.3 Update `_tool_handlers` registry: replace `get_background` with `background` handler
- [x] 4.4 Replace stub comment block in `handle_event()` with real tool loop: call `complete_with_tools()`, check for tool_calls, execute handlers, append results, repeat
- [x] 4.5 Handle multiple tool calls in a single response (execute all, append all results)
- [x] 4.6 Add tool result formatting — format memory tier data as human-readable text, empty tiers as informative messages
- [x] 4.7 Track `_characters_touched` during tool call execution for compaction scheduling

## 5. Tests

- [x] 5.1 Unit tests for `ToolCall`, `ToolResult`, `LLMToolResponse` model creation and field validation
- [x] 5.2 Unit tests for `Message.tool_result()` factory and `Message.to_dict()` with tool fields
- [x] 5.3 Unit tests for `BaseLLMClient._parse_tool_calls()` — normal, missing IDs, empty
- [x] 5.4 Unit tests for `BaseLLMClient._build_tool_response()` — text only, tool calls only, both present
- [x] 5.5 Unit tests for `OpenAIClient.complete_with_tools()` — mock httpx, verify request body includes tools, verify tool call parsing
- [x] 5.6 Unit tests for `OllamaClient.complete_with_tools()` — mock httpx, verify synthetic ID generation
- [x] 5.7 Unit tests for ConversationManager tool loop — mock `complete_with_tools()` to return tool calls then text, verify handler dispatch and message history
- [x] 5.8 Unit tests for `_handle_background()` — read/write/update actions dispatch to correct state client methods
- [x] 5.9 Verify existing `complete()` tests still pass (backward compatibility)
