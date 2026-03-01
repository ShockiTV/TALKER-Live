# force-llm-override

## Purpose

Allows operators hosting `talker_service` to override the game client's MCM LLM provider choices via `.env` variables, forcing all LLM calls through `ProxyClient` regardless of in-game settings.

## Requirements

### Requirement: Env boolean switch forces proxy

When `FORCE_PROXY_LLM=true` is set in `.env`, the service SHALL route all LLM calls through the `ProxyClient` backend, ignoring the client's MCM `model_method` selection.

#### Scenario: Force proxy enabled overrides Ollama config

- **WHEN** `FORCE_PROXY_LLM=true` is set in `.env`
- **AND** the client MCM is configured for Ollama (`model_method=2`)
- **THEN** `get_current_llm_client()` returns a `ProxyClient` instance
- **AND** the response is served from the proxy endpoint

### Requirement: Env proxy model propagates to client

When `PROXY_MODEL` is set in `.env`, the service SHALL pass this model name to the `ProxyClient` constructor payload.

#### Scenario: Custom model name used

- **WHEN** `FORCE_PROXY_LLM=true` and `PROXY_MODEL="gpt-4o"` are set in `.env`
- **THEN** the `ProxyClient` uses `"gpt-4o"` as the model name in API requests

### Requirement: Configuration schema extends Settings

The `Settings` class (pydantic-settings) SHALL include `force_proxy_llm: bool` (default `False`) and `proxy_model: str` (default `""`) fields loaded from `.env`.

#### Scenario: Settings loaded from .env

- **WHEN** the service boots
- **THEN** `settings.force_proxy_llm` and `settings.proxy_model` reflect the `.env` values

### Requirement: Override is transparent to game client

The proxy override SHALL be transparent to the Lua game client — no protocol or behaviour changes are visible to the client when the override is active.

#### Scenario: Client receives normal dialogue response

- **WHEN** `FORCE_PROXY_LLM=true` is active
- **AND** the client sends a `game.event`
- **THEN** the client receives a `dialogue.display` response indistinguishable from a non-overridden response