# Service-Level LLM Configuration Overrides Specification

## Capability Requirements

The `force-llm-override` capability allows operators hosting `talker_service` (centrally or locally) to completely intercept and replace the game client's (`talker.lua`) MCM LLM provider choices. 

| Requirement | Type | Description | P/S | Verification |
|-------------|------|-------------|-----|--------------|
| Env Boolean Switch | Functional | `FORCE_PROXY_LLM=true` in `.env` forces all connections through the `ProxyClient` backend. | P | Unit Test validation |
| Env Proxy Model | Functional | Optional `.env` variable `PROXY_MODEL="gpt-4o"` propagates down to constructor payload. | S | Unit Test validation |
| Game Overrides | Functional | Client configured for "Ollama" in MCM receives responses seamlessly from the proxy without failure. | P | Integration tests |

*P/S: Primary / Secondary

## Interaction Triggers
1. Service boots up (reads `.env`).
2. Player starts game, triggers `config.sync`.
3. Client issues prompt.
4. Python server `get_current_llm_client()` executes immediately prior to responding.

### Before this capability:
1. `__main__.py` evaluates `config_mirror` cache.
2. Extracts method (e.g., 2 for Ollama).
3. Connects to `localhost:11434`.

### After this capability:
1. `__main__.py` evaluates `config_mirror` cache.
2. Intercepts logic: `if settings.force_proxy_llm: return ProxyClient(3)`
3. Connects to custom remote URL.

## Configuration Schemas
### Extended Settings Schema
```python
class Settings(BaseSettings):
    # Proxy settings
    force_proxy_llm: bool = False
    proxy_model: str = ""
    # ... legacy proxy_endpoint and key 
```

## System Interfaces

* `talker_service/src/talker_service/config.py`: Primary loading logic for `force_proxy_llm`.
* `talker_service/src/talker_service/__main__.py`: Routing switch based purely on Python `settings` singleton.

## Assumptions & Dependencies
* `ProxyClient` remains functional as an OpenAI-compatible interface wrapper.
* Users can format GitHub PAT variables properly inside `.env`.