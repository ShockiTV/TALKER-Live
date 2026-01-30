# python-llm-client

## Purpose

Python module providing LLM API integration with provider-specific implementations for GPT, OpenRouter, Ollama, and proxy modes.

## Requirements

### LLM Client Protocol

The system MUST define an abstract `LLMClient` protocol with async completion method.

#### Scenario: Complete dialogue request with GPT
- **WHEN** the dialogue generator requests completion with GPT selected
- **THEN** the OpenAI client sends a POST to chat/completions
- **AND** returns the generated text from the response

### OpenAI Client Implementation

The system MUST implement `OpenAIClient` that reads API key and sends requests to OpenAI.

#### Scenario: Handle rate limiting
- **WHEN** OpenAI returns 429 rate limit error
- **THEN** the client waits and retries up to 3 times

### OpenRouter Client Implementation

The system MUST implement `OpenRouterClient` for OpenRouter API.

#### Scenario: OpenRouter request
- **WHEN** dialogue generation uses OpenRouter provider
- **THEN** request is sent to OpenRouter endpoint with model override

### Ollama Client Implementation

The system MUST implement `OllamaClient` for local Ollama.

#### Scenario: Ollama not running
- **WHEN** Ollama client attempts connection and Ollama is not running
- **THEN** the client raises a connection error

### Proxy Client Implementation

The system MUST implement `ProxyClient` for user-configured proxy endpoint.

#### Scenario: Proxy request
- **WHEN** proxy provider is selected
- **THEN** request is sent to configured proxy endpoint

### Client Factory

The system MUST provide `get_llm_client(provider: str) -> LLMClient` factory function.

#### Scenario: Config-driven provider selection
- **WHEN** MCM modelmethod changes from 0 to 1
- **THEN** subsequent get_llm_client calls return OpenRouterClient

### Timeout Handling

The system MUST handle LLM request timeouts gracefully.

#### Scenario: Complete request with timeout
- **WHEN** an LLM request exceeds 60 seconds
- **THEN** the client raises a timeout error
