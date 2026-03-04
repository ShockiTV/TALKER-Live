## 1. SDK Client Setup

- [x] 1.1 Replace httpx import with `openai.AsyncOpenAI` in `openai_client.py`; add `import openai` and `import json`
- [x] 1.2 Initialize `self._client = AsyncOpenAI(api_key=..., base_url=..., max_retries=0)` in `__init__`; add `_last_response_id: str | None = None`
- [x] 1.3 Add private `_convert_tools()` method to transform Chat Completions tool format to Responses API format

## 2. Migrate complete() to SDK

- [x] 2.1 Rewrite `complete()` to use `self._client.chat.completions.create()` instead of httpx POST
- [x] 2.2 Map SDK exceptions: `openai.RateLimitError` → `RateLimitError`, `openai.AuthenticationError` → `AuthenticationError`, `openai.APITimeoutError` → `TimeoutError`, `openai.APIError` → `LLMError`

## 3. Migrate complete_with_tools() to Responses API

- [x] 3.1 Rewrite `complete_with_tools()` to use `self._client.responses.create()` with `input`, `model`, `temperature`, `tools` (converted), and `truncation="auto"`
- [x] 3.2 Implement `previous_response_id` threading: pass `_last_response_id` when set, update after each successful response
- [x] 3.3 Implement Responses API output parsing: `ResponseFunctionToolCall` → `ToolCall`, `ResponseOutputMessage` → text extraction
- [x] 3.4 Remove `prune_conversation()` call from `complete_with_tools()`; keep `_conversation` append for tool result tracking within a single tool loop
- [x] 3.5 Add `NotFoundError` recovery: catch invalid `previous_response_id`, clear it, retry without threading

## 4. State Management

- [x] 4.1 Update `reset_conversation()` to also clear `_last_response_id`
- [x] 4.2 Verify `get_conversation()` still works (returns `_conversation` copy for debugging)

## 5. Update Tests

- [x] 5.1 Rewrite `TestOpenAIClient` in `test_llm_clients.py`: mock `AsyncOpenAI.chat.completions.create` instead of `httpx.AsyncClient.post`
- [x] 5.2 Rewrite `TestOpenAICompleteWithTools` in `test_tool_calling.py`: mock `AsyncOpenAI.responses.create` with Responses API output format
- [x] 5.3 Add test for tool definition format conversion (`_convert_tools`)
- [x] 5.4 Add test for `previous_response_id` threading (first call without, second call with)
- [x] 5.5 Add test for `NotFoundError` recovery (auto-retry without `previous_response_id`)
- [x] 5.6 Verify all non-OpenAI tests still pass unchanged (OpenRouter, Ollama, Proxy)

## 6. Validation

- [x] 6.1 Run full Python test suite and confirm all tests pass
- [x] 6.2 Remove unused `import httpx` from `openai_client.py` if no longer needed
