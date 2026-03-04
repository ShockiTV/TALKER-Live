# llm-tool-calling (delta)

## MODIFIED Requirements

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
