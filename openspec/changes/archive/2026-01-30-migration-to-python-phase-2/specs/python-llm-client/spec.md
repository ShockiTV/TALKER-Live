# python-llm-client

## Overview

Python module providing LLM API integration with provider-specific implementations for GPT, OpenRouter, Ollama, and proxy modes.

## Requirements

### ADDED: LLM Client Protocol

The system MUST define an abstract `LLMClient` protocol with:
- `async complete(messages: list[Message], opts: LLMOptions) -> str` method
- Support for temperature, max_tokens, and model selection via opts
- Timeout handling (default 60 seconds, configurable via MCM)

### ADDED: OpenAI Client Implementation

The system MUST implement `OpenAIClient` that:
- Reads API key from `openai_api_key.txt` or environment variable
- Sends requests to OpenAI chat completions API
- Handles rate limiting with exponential backoff
- Logs request/response for debugging

### ADDED: OpenRouter Client Implementation

The system MUST implement `OpenRouterClient` that:
- Reads API key from MCM config or environment variable
- Sends requests to OpenRouter API endpoint
- Supports model override from config
- Handles provider-specific response format

### ADDED: Ollama Client Implementation

The system MUST implement `OllamaClient` that:
- Connects to local Ollama endpoint (default localhost:11434)
- Supports custom endpoint configuration
- Handles streaming responses (accumulate to final string)
- Gracefully fails if Ollama not running

### ADDED: Proxy Client Implementation

The system MUST implement `ProxyClient` that:
- Sends requests to user-configured proxy endpoint
- Passes through model/temperature settings
- Supports OpenAI-compatible proxy APIs

### ADDED: Client Factory

The system MUST provide `get_llm_client(provider: str) -> LLMClient` that:
- Returns appropriate client based on MCM `modelmethod` setting
- Values: 0=GPT, 1=OpenRouter, 2=Ollama, 3=Proxy
- Caches client instances for reuse

## Scenarios

#### Complete dialogue request with GPT

WHEN the dialogue generator requests completion with GPT selected
THEN the OpenAI client sends a POST to chat/completions
AND returns the generated text from the response

#### Complete request with timeout

WHEN an LLM request exceeds 60 seconds
THEN the client raises a timeout error
AND the caller handles gracefully (no dialogue generated)

#### Handle rate limiting

WHEN OpenAI returns 429 rate limit error
THEN the client waits and retries up to 3 times
AND logs each retry attempt

#### Ollama not running

WHEN Ollama client attempts connection and Ollama is not running
THEN the client raises a connection error
AND the caller handles gracefully (no dialogue generated)

#### Config-driven provider selection

WHEN MCM modelmethod changes from 0 to 1
THEN subsequent get_llm_client calls return OpenRouterClient
AND the switch is seamless (no restart required)
