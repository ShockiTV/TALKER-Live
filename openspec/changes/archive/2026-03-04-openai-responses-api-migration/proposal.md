## Why

The OpenAI client (`openai_client.py`) hand-rolls every HTTP call via `httpx.post()` to the Chat Completions endpoint (`/v1/chat/completions`). This means every `complete_with_tools()` call re-sends the full accumulated conversation history as input tokens — growing to 64–96k tokens per call in steady-state play sessions. The OpenAI Responses API (`/v1/responses`) provides server-side conversation threading via `previous_response_id`, eliminating redundant re-transmission of context. This is the dominant cost driver for OpenAI users and switching will reduce input token spend by ~10x during tool-calling dialogue loops. The `openai` SDK (v2.24+) is already a project dependency but unused by the LLM client.

## What Changes

- Replace raw `httpx` HTTP calls in `OpenAIClient` with the official `openai.AsyncOpenAI` SDK client
- `complete()` uses `client.chat.completions.create()` (Chat Completions API — one-shot, no benefit from Responses)
- `complete_with_tools()` uses `client.responses.create()` (Responses API — server-side conversation state via `previous_response_id`)
- Track `_last_response_id` per client instance for Responses API conversation threading
- Skip client-side pruning (`pruning.py`) when using Responses API — server manages context window
- Retain pruning module for other providers (OpenRouter, Ollama, Proxy) — no changes to those
- Convert Responses API `ResponseFunctionToolCall` / `ResponseOutputMessage` output types into existing `ToolCall` / `LLMToolResponse` models
- Convert existing OpenAI-format tool definitions (`{"type": "function", "function": {...}}`) to Responses API function tool format
- Map `reset_conversation()` to clear `_last_response_id` (starts fresh server-side chain)
- Update all OpenAI-specific tests to mock SDK calls instead of `httpx.AsyncClient.post`

## Capabilities

### New Capabilities
- `openai-responses-api`: OpenAI Responses API integration for `complete_with_tools()` — server-side conversation state, `previous_response_id` threading, SDK-based error handling

### Modified Capabilities
- `python-llm-client`: OpenAI client implementation changes from raw httpx to SDK; `complete()` uses `chat.completions.create()`, `complete_with_tools()` uses `responses.create()`
- `llm-tool-calling`: OpenAI's `complete_with_tools()` changes from Chat Completions to Responses API; response parsing changes from `choices[0].message` to `Response.output` items; tool definitions converted to Responses API format

## Impact

- **Code**: `talker_service/src/talker_service/llm/openai_client.py` (major rewrite), `pruning.py` (bypassed for OpenAI)
- **Tests**: `tests/test_llm_clients.py` and `tests/test_tool_calling.py` — OpenAI-specific tests need SDK mocking
- **Dependencies**: No new deps — `openai>=1.0.0` already in `pyproject.toml`, `httpx` import removed from openai_client
- **API**: No changes to `LLMClient` protocol or `BaseLLMClient` interface — other providers unaffected
- **Config**: `openai_endpoint` setting continues to work via `AsyncOpenAI(base_url=...)` — Azure Copilot endpoints supported
