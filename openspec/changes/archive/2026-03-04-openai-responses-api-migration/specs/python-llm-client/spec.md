# python-llm-client (delta)

## MODIFIED Requirements

### OpenAI Client Implementation

The system MUST implement `OpenAIClient` that reads API key and uses the `openai.AsyncOpenAI` SDK client for all API calls. The client SHALL initialize an `AsyncOpenAI` instance with `api_key`, optional `base_url` (from `openai_endpoint` setting), and `max_retries=0`. The `complete()` method SHALL use `client.chat.completions.create()` and return text content. SDK exceptions (`openai.RateLimitError`, `openai.AuthenticationError`, `openai.APITimeoutError`) SHALL be caught and mapped to the existing `RateLimitError`, `AuthenticationError`, and `TimeoutError` types.

#### Scenario: Handle rate limiting
- **WHEN** OpenAI returns 429 rate limit error (SDK raises `openai.RateLimitError`)
- **THEN** the client waits and retries up to 3 times with exponential backoff

#### Scenario: Successful completion via SDK
- **WHEN** `complete()` is called with messages
- **THEN** `client.chat.completions.create()` SHALL be called (not raw httpx POST)
- **AND** the text content from `choices[0].message.content` SHALL be returned as a string

#### Scenario: Custom endpoint passed to SDK
- **WHEN** `OpenAIClient` is created with a custom `endpoint` (e.g., Azure Copilot URL)
- **THEN** the `AsyncOpenAI` client SHALL be initialized with `base_url` set to that endpoint
