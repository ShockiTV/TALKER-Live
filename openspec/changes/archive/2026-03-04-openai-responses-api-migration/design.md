## Context

The `OpenAIClient` currently hand-rolls every HTTP call via `httpx.AsyncClient.post()` to the Chat Completions endpoint (`/v1/chat/completions`). The persistent `_conversation` list accumulates messages across game events and is re-sent in full on every API call — growing to 64–96k input tokens in steady-state play sessions. This is the dominant cost driver for OpenAI users.

The `openai` Python SDK (v2.24+) is already a project dependency (`openai>=1.0.0` in `pyproject.toml`) but is only used by the STT Whisper API provider — the LLM client never touches it.

The OpenAI Responses API (`/v1/responses`) is a newer endpoint that supports server-side conversation threading via `previous_response_id`. After the first turn, subsequent calls send only new input — the server retains full context. This eliminates redundant re-transmission and reduces input token spend by ~10x during multi-turn tool-calling dialogue loops.

### Current call flow (complete_with_tools)
1. Caller builds `messages: list[Message]` (system prompt + event + recent history)
2. `complete_with_tools()` appends to `_conversation`, prunes if >96k tokens
3. Serializes entire `_conversation` via `to_dict()` → JSON
4. `httpx.post()` to Chat Completions with full history
5. Parses `choices[0].message` → `LLMToolResponse`
6. Appends assistant reply to `_conversation`
7. Caller handles tool calls, adds tool results as Messages, calls again

### Other providers
OpenRouter, Ollama, and Proxy clients also implement `complete_with_tools()` via httpx to Chat Completions-compatible endpoints. These are **not** changing — only the OpenAI client is affected.

## Goals / Non-Goals

**Goals:**
- Replace raw httpx in `OpenAIClient` with the official `openai.AsyncOpenAI` SDK client
- `complete()` uses `client.chat.completions.create()` — one-shot calls, no benefit from conversation threading
- `complete_with_tools()` uses `client.responses.create()` — server-side state via `previous_response_id`
- Reduce input token spend by ~10x during tool-calling dialogue loops
- Map Responses API output types (`ResponseFunctionToolCall`, `ResponseOutputMessage`) to existing `ToolCall` / `LLMToolResponse` models
- Retain the `LLMClient` protocol and `BaseLLMClient` interface unchanged
- Azure Copilot endpoint support via `AsyncOpenAI(base_url=...)`
- Update all OpenAI-specific tests to mock SDK calls instead of httpx

**Non-Goals:**
- No changes to OpenRouter, Ollama, or Proxy clients
- No streaming support (Responses API supports it but not needed now)
- No changes to `LLMClient` protocol signature
- No changes to `conversation.py` caller logic (it continues building `messages` the same way)
- No Responses API for `complete()` (one-shot memory compression has no benefit from threading)

## Decisions

### D1: SDK for both complete() and complete_with_tools()

**Choice:** Use `AsyncOpenAI` SDK client for all OpenAI API calls. `complete()` uses `client.chat.completions.create()`. `complete_with_tools()` uses `client.responses.create()`.

**Alternative considered:** Keep httpx for `complete()` and only use SDK for Responses. Rejected because using the SDK for both simplifies error handling (SDK has built-in retry, auth validation, and typed exceptions) and removes the httpx dependency from the OpenAI client entirely.

**Alternative considered:** Use Responses API for `complete()` too. Rejected because one-shot calls (memory compression) don't benefit from conversation threading, and Chat Completions is simpler for single-turn use.

### D2: Server-side conversation state replaces client-side _conversation

**Choice:** Replace `_conversation: list[Message]` with `_last_response_id: str | None`. On first `complete_with_tools()` call, send `input=messages` (full context). On subsequent calls in the same session, send `input=new_messages` + `previous_response_id=self._last_response_id`. The server retains all prior context.

**Rationale:** This is the core cost reduction. Instead of re-sending 64–96k tokens on every call, subsequent turns send only the new tool results or user messages (~200–500 tokens).

### D3: Bypass pruning for OpenAI Responses API

**Choice:** Skip `prune_conversation()` in `complete_with_tools()` when Responses API is used — server manages context window via `truncation` parameter. Keep the pruning module intact for other providers.

**Rationale:** Responses API has a `truncation` parameter (`"auto"` or explicit) that handles context window management server-side. Client-side pruning would conflict with server-side state.

### D4: Tool definition format conversion

**Choice:** Convert existing Chat Completions tool definitions `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}` to Responses API format `{"type": "function", "name": ..., "description": ..., "parameters": ...}` inside `OpenAIClient.complete_with_tools()`. The caller continues passing Chat Completions format — conversion is internal.

**Rationale:** Keeps the `LLMClient` protocol unchanged. All providers receive the same tool definitions; only OpenAI internally transforms them.

### D5: Response parsing — Responses API output

**Choice:** Parse `Response.output` items instead of `choices[0].message`. Map `ResponseFunctionToolCall` → `ToolCall(id=item.call_id, name=item.name, arguments=json.loads(item.arguments))`. Map `ResponseOutputMessage` → extract text from `content[0].text`. Implement this as private methods in `OpenAIClient`, not in `BaseLLMClient`.

**Rationale:** Responses API output format is fundamentally different from Chat Completions. The shared `_build_tool_response()` static method in `BaseLLMClient` assumes Chat Completions format (`choices[0].message`). OpenAI needs its own parsing; other providers still use the shared helper.

### D6: reset_conversation clears server-side state reference

**Choice:** `reset_conversation()` sets `_last_response_id = None` and clears `_conversation`. Next call starts a fresh conversation chain with no `previous_response_id`.

**Rationale:** Server-side conversations are immutable — you can't delete them. But by dropping the `_last_response_id`, the next call creates a new independent conversation chain. Old server-side data expires via OpenAI's retention policy.

### D7: Azure/custom endpoint via AsyncOpenAI base_url

**Choice:** Pass `openai_endpoint` setting as `base_url` kwarg to `AsyncOpenAI(base_url=..., api_key=...)`. The SDK handles path construction. No fallback to Chat Completions is needed — Azure Copilot endpoints support the Responses API.

### D8: SDK-based error handling replaces manual HTTP status checks

**Choice:** Use SDK exceptions (`openai.RateLimitError`, `openai.AuthenticationError`, `openai.APITimeoutError`, `openai.APIError`) instead of checking `response.status_code`. Map to existing `RateLimitError`, `AuthenticationError`, `LLMError` from `base.py`.

**Rationale:** More robust — SDK handles edge cases (retries, malformed responses) that manual httpx code doesn't.

## Risks / Trade-offs

**[Risk] Responses API state is server-side and opaque** → Mitigation: Track `_last_response_id` locally. If it becomes invalid (e.g., server purges old conversations), the SDK will raise an error. Catch `openai.NotFoundError` and fall back to starting a fresh conversation (clear `_last_response_id`, retry without `previous_response_id`).

**[Risk] SDK retry logic may conflict with our custom retry loop** → Mitigation: Disable SDK's built-in retries (`max_retries=0` on `AsyncOpenAI`) and keep our existing exponential backoff loop. This preserves consistent behavior across all providers.

**[Risk] Tool definition format mismatch** → Mitigation: Conversion is a simple dict restructure (move `function.name`, `function.description`, `function.parameters` up one level). Unit test the conversion function.

**[Risk] Existing tests mock httpx directly** → Mitigation: Rewrite OpenAI-specific tests to mock `AsyncOpenAI.chat.completions.create` and `AsyncOpenAI.responses.create`. Use `unittest.mock.AsyncMock`. Non-OpenAI tests remain unchanged.

**[Trade-off] Server-side state means we can't inspect full conversation locally** → Acceptable: `_conversation` was only used for sending to the API and debugging. For debugging, the `_last_response_id` can be used to retrieve the conversation via OpenAI's API if needed.

## Open Questions

None — all design decisions were resolved in the exploration phase.
