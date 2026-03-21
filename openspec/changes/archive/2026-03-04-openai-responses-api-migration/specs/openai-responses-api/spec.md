# openai-responses-api

## Purpose

OpenAI Responses API integration for the `OpenAIClient.complete_with_tools()` method. Provides server-side conversation threading via `previous_response_id`, SDK-based API calls, and Responses API output parsing — replacing raw httpx calls to the Chat Completions endpoint.

## Requirements

### Requirement: SDK client initialization

The `OpenAIClient` SHALL initialize an `openai.AsyncOpenAI` client instance with `api_key`, `base_url` (from `openai_endpoint` setting when non-empty), and `max_retries=0` (retries handled by the existing client-side loop).

#### Scenario: Default endpoint
- **WHEN** `OpenAIClient` is created with no custom endpoint
- **THEN** an `AsyncOpenAI` client SHALL be created with no `base_url` override (uses OpenAI default)
- **AND** `max_retries` SHALL be `0`

#### Scenario: Custom endpoint (Azure)
- **WHEN** `OpenAIClient` is created with `endpoint="https://my-copilot.openai.azure.com/v1"`
- **THEN** the `AsyncOpenAI` client SHALL be created with `base_url` set to that endpoint

### Requirement: complete() uses Chat Completions SDK

The `OpenAIClient.complete()` method SHALL use `self._client.chat.completions.create()` instead of raw httpx POST. It SHALL pass `model`, `messages`, `temperature`, and optionally `max_tokens`. It SHALL return `response.choices[0].message.content` as a string.

#### Scenario: Successful one-shot completion
- **WHEN** `complete()` is called with messages
- **THEN** `self._client.chat.completions.create()` SHALL be called with the serialized messages
- **AND** the text content from `choices[0].message.content` SHALL be returned

#### Scenario: Rate limit on complete()
- **WHEN** the SDK raises `openai.RateLimitError` during `complete()`
- **THEN** the client SHALL retry with exponential backoff up to `max_retries` times
- **AND** raise `RateLimitError` if retries are exhausted

#### Scenario: Authentication failure on complete()
- **WHEN** the SDK raises `openai.AuthenticationError`
- **THEN** the client SHALL raise `AuthenticationError` immediately (no retry)

#### Scenario: Timeout on complete()
- **WHEN** the SDK raises `openai.APITimeoutError`
- **THEN** the client SHALL raise `TimeoutError`

### Requirement: complete_with_tools() uses Responses API

The `OpenAIClient.complete_with_tools()` method SHALL use `self._client.responses.create()` instead of raw httpx POST to Chat Completions. It SHALL send `input` (messages), `model`, `temperature`, `tools` (converted to Responses format), and optionally `previous_response_id` for conversation threading.

#### Scenario: First call in session (no previous response)
- **WHEN** `complete_with_tools()` is called and `_last_response_id` is None
- **THEN** `responses.create()` SHALL be called with `input=messages` and no `previous_response_id`
- **AND** `_last_response_id` SHALL be set to `response.id` from the result

#### Scenario: Subsequent call with previous response
- **WHEN** `complete_with_tools()` is called and `_last_response_id` is set
- **THEN** `responses.create()` SHALL be called with `previous_response_id=self._last_response_id`
- **AND** `input` SHALL contain only the new messages (not the full history)
- **AND** `_last_response_id` SHALL be updated to the new `response.id`

#### Scenario: Rate limit on complete_with_tools()
- **WHEN** the SDK raises `openai.RateLimitError` during `complete_with_tools()`
- **THEN** the client SHALL retry with exponential backoff up to `max_retries` times

### Requirement: Responses API output parsing

The client SHALL parse `Response.output` items to construct `LLMToolResponse`. `ResponseFunctionToolCall` items SHALL be converted to `ToolCall` objects. `ResponseOutputMessage` items SHALL have their text content extracted.

#### Scenario: Tool calls in response
- **WHEN** the Responses API returns output items containing `ResponseFunctionToolCall` objects
- **THEN** each SHALL be parsed into `ToolCall(id=item.call_id, name=item.name, arguments=json.loads(item.arguments))`
- **AND** `LLMToolResponse(text=None, tool_calls=[...])` SHALL be returned

#### Scenario: Text-only response
- **WHEN** the Responses API returns output items containing a `ResponseOutputMessage` with text content
- **THEN** the text SHALL be extracted from `content[0].text`
- **AND** `LLMToolResponse(text=extracted_text, tool_calls=[])` SHALL be returned

#### Scenario: Mixed output (text + tool calls)
- **WHEN** the response contains both text messages and function tool calls
- **THEN** tool calls SHALL take priority (matching existing `LLMToolResponse` semantics)

### Requirement: Tool definition format conversion

The client SHALL convert Chat Completions format tool definitions to Responses API format internally. The input format `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}` SHALL be converted to `{"type": "function", "name": ..., "description": ..., "parameters": ...}`.

#### Scenario: Tool definition converted
- **WHEN** `complete_with_tools()` receives tools in Chat Completions format
- **THEN** each tool SHALL be converted to Responses API format before passing to `responses.create()`
- **AND** the `name`, `description`, and `parameters` fields SHALL be preserved exactly

### Requirement: Conversation state management

The client SHALL track `_last_response_id: str | None` for Responses API conversation threading. `reset_conversation()` SHALL clear this ID, starting a fresh conversation chain on the next call.

#### Scenario: reset_conversation clears state
- **WHEN** `reset_conversation()` is called
- **THEN** `_last_response_id` SHALL be set to None
- **AND** `_conversation` list SHALL be cleared
- **AND** the next `complete_with_tools()` call SHALL start a fresh conversation (no `previous_response_id`)

#### Scenario: Invalid previous_response_id recovery
- **WHEN** the Responses API returns a NotFoundError because `previous_response_id` references an expired or invalid conversation
- **THEN** the client SHALL clear `_last_response_id` and retry the call without `previous_response_id` (starting a fresh chain)

### Requirement: Pruning bypass for Responses API

The `complete_with_tools()` method SHALL NOT call `prune_conversation()` when using the Responses API. Server-side context management via `truncation` replaces client-side pruning.

#### Scenario: No pruning during Responses API calls
- **WHEN** `complete_with_tools()` is called on `OpenAIClient`
- **THEN** `prune_conversation()` SHALL NOT be invoked
- **AND** the `truncation` parameter SHALL be set to `"auto"` in the `responses.create()` call

### Requirement: httpx removal from OpenAI client

The `OpenAIClient` module SHALL NOT import or use `httpx`. All HTTP communication SHALL go through the `openai.AsyncOpenAI` SDK client.

#### Scenario: No httpx dependency
- **WHEN** `openai_client.py` is inspected
- **THEN** there SHALL be no `import httpx` statement
- **AND** all API calls SHALL use `self._client` (AsyncOpenAI instance)
