# Proposal: Force LLM Service Override

## What We're Building
A mechanism in the Python `talker_service` to completely override the player's MCM LLM configuration via `.env` variables. This will force the service to use a specific LLM provider, completely ignoring the `model_method` and `model_name` sent by the game client via `config.sync` or `config.update`. The primary use case is forcing connections through the GitHub Copilot Models endpoint using a Personal Access Token (PAT).

## Why We're Building It (The Problem)
Currently, the Game Client (Lua via MCM settings) acts as the single source of truth for the LLM configuration. When a player connects to a remote LLM server, the Lua side sends a `config.sync` payload which tells the server which provider and model to use, which is tracked by `ConfigMirror` in Python. 
If someone wants to host the LLM service centrally (like for the `bridge-remote-url` feature), but wants to provide the processing themselves (e.g., using their GitHub PAT on a centralized backend), they cannot currently hardcode the backend to ignore what the player's game is asking for. If the local player's MCM is set to "Local Ollama", the server will attempt to query a local Ollama instance on the server, rather than the intended GitHub Copilots API. 

## Scope

### In Scope
* Adding new environment variables to force the LLM proxy mode (e.g., `FORCE_PROXY_LLM=true`).
* Intercepting how the `get_current_llm_client()` function in `talker_service/src/talker_service/__main__.py` pulls data from the `ConfigMirror`.
* Updating `__main__.py` to respect the `.env` override, regardless of the `config_mirror`'s state for LLM config.
* Reusing the existing `ProxyClient` (Method 3) to execute GitHub PAT requests, as it already supports OpenAI-compatible payloads.

### Out of Scope
* Overriding other non-LLM MCM settings (like TTS settings, UI toggles, Log Levels).
* Building a new LLM Client (the proxy client works fine).
* Making changes to `talker_bridge` (this is purely handled within `talker_service`).
* Game side / Lua code changes.

## Potential Challenges
*   **Initialization Timing:** We must ensure the forced provider isn't clobbered when a late `config.sync` packet clears the client cache via `clear_client_cache()`. Since `get_current_llm_client` evaluates the settings right before creating the client, intercepting it there should mitigate timing issues.
*   **Proxy Authentication Header:** The GitHub Models API requires a standard `Bearer <PAT>` HTTP header on an OpenAI-compatible URL. We need to verify `ProxyClient` handles authentication headers correctly based on `proxy_api_key`.

## Context References
*   `talker_service/src/talker_service/config.py`: Service-level `.env` loader.
*   `talker_service/src/talker_service/__main__.py`: Houses `get_current_llm_client()`.
*   `talker_service/src/talker_service/handlers/config.py`: `ConfigMirror` cache where game variables live.
*   `talker_service/src/talker_service/llm/proxy_client.py`: The client that handles standard OpenAI payloads to custom endpoints.