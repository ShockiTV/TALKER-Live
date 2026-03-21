# llm-tool-calling

## Purpose

LLM client infrastructure for tool/function calling across all providers: tool definitions schema, structured response parsing (text OR tool calls), Message model extensions for tool content, and `complete_with_tools()` method on all LLM clients.

## Requirements

### Requirement: ToolCall and ToolResult models

The system SHALL provide `ToolCall` and `ToolResult` dataclasses in `llm/models.py`. `ToolCall` SHALL contain `id` (string), `name` (string), and `arguments` (dict). `ToolResult` SHALL contain `tool_call_id` (string), `name` (string), and `content` (string — JSON-serialized result).

#### Scenario: ToolCall created from API response
- **WHEN** an LLM API returns a tool call with id="call_abc123", name="get_memories", arguments={"character_id": "12467", "tiers": ["events"]}
- **THEN** a `ToolCall` SHALL be created with those exact fields
- **AND** `arguments` SHALL be a parsed dict (not a JSON string)

#### Scenario: ToolResult created for tool response
- **WHEN** a tool handler returns result data {"events": [...]}
- **THEN** a `ToolResult` SHALL be created with the originating `tool_call_id`, `name`, and JSON-serialized `content`

### Requirement: LLMToolResponse model

The system SHALL provide an `LLMToolResponse` dataclass with `text: str | None` and `tool_calls: list[ToolCall]`. Exactly one SHALL be populated: if `tool_calls` is non-empty, `text` SHALL be None; if `text` is set, `tool_calls` SHALL be empty.

#### Scenario: Text-only response
- **WHEN** an LLM returns content with finish_reason="stop"
- **THEN** `LLMToolResponse` SHALL have `text` set to the content string and `tool_calls` as an empty list

#### Scenario: Tool calls response
- **WHEN** an LLM returns tool_calls with finish_reason="tool_calls"
- **THEN** `LLMToolResponse` SHALL have `text` as None and `tool_calls` populated

#### Scenario: Response has both text and tool calls
- **WHEN** an LLM returns both content text and tool_calls array
- **THEN** `LLMToolResponse` SHALL prioritize `tool_calls` (set `text` to None) since the LLM is requesting tool execution

### Requirement: Message model tool extensions

The `Message` dataclass SHALL be extended with optional fields: `tool_calls: list[ToolCall] | None` (default None), `tool_call_id: str | None` (default None), `name: str | None` (default None). The `to_dict()` method SHALL include these fields only when they are not None. A new `Message.tool_result(tool_call_id, name, content)` class method SHALL create a message with role="tool".

#### Scenario: Standard message serialization unchanged
- **WHEN** `Message(role="user", content="hello").to_dict()` is called
- **THEN** the result SHALL be `{"role": "user", "content": "hello"}` with no extra fields

#### Scenario: Assistant message with tool calls serialized
- **WHEN** an assistant message has `tool_calls=[ToolCall(id="call_1", name="get_memories", arguments={...})]`
- **THEN** `to_dict()` SHALL include a `tool_calls` array with objects containing `id`, `type: "function"`, and `function: {name, arguments}`

#### Scenario: Tool result message created
- **WHEN** `Message.tool_result("call_1", "get_memories", '{"events": [...]}')` is called
- **THEN** the message SHALL have role="tool", content=the JSON string, tool_call_id="call_1", name="get_memories"

#### Scenario: Tool result message serialized
- **WHEN** a tool result message is serialized via `to_dict()`
- **THEN** the dict SHALL include `role`, `content`, `tool_call_id`, and `name` fields

### Requirement: LLMClient protocol complete_with_tools method

The `LLMClient` protocol and `BaseLLMClient` abstract class SHALL define a `complete_with_tools()` method that accepts `messages: list[Message]`, `tools: list[dict]`, and optional `opts: LLMOptions`. It SHALL return `LLMToolResponse`.

#### Scenario: Protocol defines complete_with_tools
- **WHEN** code checks `isinstance(client, LLMClient)`
- **THEN** the client SHALL have both `complete()` and `complete_with_tools()` methods

#### Scenario: complete_with_tools called with tools
- **WHEN** `complete_with_tools(messages, tools=[{...}])` is called
- **THEN** the LLM provider SHALL include the `tools` array in the API request body

#### Scenario: complete_with_tools returns LLMToolResponse
- **WHEN** the LLM responds
- **THEN** the return value SHALL be an `LLMToolResponse` instance (not a plain string)

### Requirement: OpenAI client complete_with_tools implementation

The `OpenAIClient` SHALL implement `complete_with_tools()` using the Responses API (`client.responses.create()`) instead of raw httpx POST to Chat Completions. It SHALL convert Chat Completions format tool definitions to Responses API format internally. It SHALL track `_last_response_id` for server-side conversation threading. It SHALL parse `Response.output` items — mapping `ResponseFunctionToolCall` to `ToolCall` and `ResponseOutputMessage` to text content. It SHALL reuse the existing retry logic (exponential backoff on `openai.RateLimitError`). It SHALL NOT call `prune_conversation()` — server-side context management via `truncation="auto"` replaces client-side pruning.

#### Scenario: OpenAI tool call response parsed (Responses API)
- **WHEN** the Responses API returns `ResponseFunctionToolCall` items in `response.output`
- **THEN** each item SHALL be parsed into `ToolCall(id=item.call_id, name=item.name, arguments=json.loads(item.arguments))`
- **AND** `LLMToolResponse(text=None, tool_calls=[...])` SHALL be returned

#### Scenario: OpenAI text response returned (Responses API)
- **WHEN** the Responses API returns a `ResponseOutputMessage` in `response.output` with no tool calls
- **THEN** the text SHALL be extracted from `content[0].text`
- **AND** `LLMToolResponse(text=extracted, tool_calls=[])` SHALL be returned

#### Scenario: OpenAI rate limit retried
- **WHEN** the SDK raises `openai.RateLimitError` during a `complete_with_tools` call
- **THEN** the same exponential backoff retry logic as `complete()` SHALL apply

#### Scenario: Tool definitions converted to Responses format
- **WHEN** `complete_with_tools()` receives tools in Chat Completions format `{"type": "function", "function": {"name": ..., "parameters": ...}}`
- **THEN** the client SHALL convert each to Responses format `{"type": "function", "name": ..., "parameters": ...}` before calling `responses.create()`

#### Scenario: Server-side conversation threading
- **WHEN** `complete_with_tools()` is called after a previous successful call
- **THEN** `responses.create()` SHALL include `previous_response_id` from the last response
- **AND** `input` SHALL contain only the new messages (not the full accumulated history)

#### Scenario: No pruning for OpenAI
- **WHEN** `complete_with_tools()` is called on `OpenAIClient`
- **THEN** `prune_conversation()` SHALL NOT be invoked
- **AND** `truncation="auto"` SHALL be passed to `responses.create()`

### Requirement: OpenRouter client complete_with_tools implementation

The `OpenRouterClient` SHALL implement `complete_with_tools()` using the same OpenAI-compatible format since OpenRouter supports tool calling via the same API shape.

#### Scenario: OpenRouter tool call parsed
- **WHEN** OpenRouter returns tool_calls in the response
- **THEN** they SHALL be parsed identically to OpenAI format

### Requirement: Ollama client complete_with_tools implementation

The `OllamaClient` SHALL implement `complete_with_tools()` by passing `tools` in the `/api/chat` request body. Ollama supports OpenAI-compatible tool calling since version 0.3+.

#### Scenario: Ollama tool call parsed
- **WHEN** Ollama returns `message.tool_calls` in the response
- **THEN** each tool call SHALL be parsed into `ToolCall` with synthetic `id` if not provided by Ollama

#### Scenario: Ollama model without tool support
- **WHEN** the Ollama model does not support tool calling
- **THEN** it SHALL return a text response and `LLMToolResponse(text=..., tool_calls=[])` SHALL be returned

### Requirement: Proxy client complete_with_tools implementation

The `ProxyClient` SHALL implement `complete_with_tools()` using OpenAI-compatible format. It SHALL include `tools` in the request body if the endpoint supports it.

#### Scenario: Proxy tool call response
- **WHEN** the proxy returns OpenAI-format tool calls
- **THEN** they SHALL be parsed into `ToolCall` objects

#### Scenario: Proxy text-only response
- **WHEN** the proxy returns only text content (no tool_calls key)
- **THEN** `LLMToolResponse(text=content, tool_calls=[])` SHALL be returned

### Requirement: Tool call ID generation for providers without IDs

When an LLM provider returns tool calls without an `id` field, the client SHALL generate a synthetic ID using `f"call_{uuid4().hex[:8]}"` to ensure tool result messages can reference the call.

#### Scenario: Missing tool call ID
- **WHEN** Ollama returns a tool call without an `id` field
- **THEN** a synthetic ID like "call_a1b2c3d4" SHALL be generated
- **AND** the `ToolCall.id` SHALL be set to this synthetic value
