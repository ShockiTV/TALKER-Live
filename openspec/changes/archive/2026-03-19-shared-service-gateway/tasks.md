## 1. Caddy API Gateway Routes

- [x] 1.1 Add `/api/tts/*` route block in Caddyfile — JWT gate (player role), strip prefix, proxy to `tts-service:8100`, inject `X-Player-ID`
- [x] 1.2 Add `/api/stt/*` route block in Caddyfile — JWT gate, strip prefix, proxy to `stt-service:8200`, inject `X-Player-ID`
- [x] 1.3 Add `/api/embed/*` route block in Caddyfile — JWT gate, strip prefix, whitelist only `/api/embeddings` and `/api/tags`, respond 403 for all other paths, inject `X-Player-ID`
- [x] 1.4 Verify Caddy access logging includes player ID and path for all API routes

## 2. Python KeycloakAuth Module

- [x] 2.1 Create `talker_service/src/talker_service/auth/__init__.py` and `keycloak.py` with `KeycloakAuth(httpx.Auth)` class — constructor accepts `token_url`, `client_id`, `client_secret`, `username`, `password`
- [x] 2.2 Implement lazy ROPC grant on first request — POST `grant_type=password` to token URL, cache `access_token`, `refresh_token`, and computed expiry timestamps
- [x] 2.3 Implement token reuse — return cached access_token when not expired
- [x] 2.4 Implement proactive refresh — use `grant_type=refresh_token` when access_token expired but refresh_token valid, fall back to full ROPC if both expired
- [x] 2.5 Implement 401 retry — clear cache and retry once with fresh token on upstream 401
- [x] 2.6 Implement error handling — log WARNING and proceed without Authorization header when token endpoint is unreachable or returns error
- [x] 2.7 Write tests for KeycloakAuth: lazy init, caching, refresh, 401 retry, error fallback, no-auth when credentials empty

## 3. Python Config & SERVICE_HUB_URL

- [x] 3.1 Add `SERVICE_HUB_URL` field to `Settings` in `config.py` (str, default empty)
- [x] 3.2 Add URL derivation validators — when `SERVICE_HUB_URL` set and per-service URLs empty: derive `tts_service_url`, `stt_endpoint`, `ollama_base_url`
- [x] 3.3 Add connection/auth fields to `ConfigMirror` model in `models/config.py`: `service_type`, `service_hub_url`, `branch`, `custom_branch`, `auth_username`, `auth_password`, `auth_client_id`, `auth_client_secret`, `llm_timeout`, `state_query_timeout`
- [x] 3.4 Update `handle_config_sync` to support MCM `service_hub_url` overriding `.env` `SERVICE_HUB_URL` derivation
- [x] 3.5 Add `SERVICE_HUB_URL` to `.env.example` (uncommented with default `https://talker-live.duckdns.org`)
- [x] 3.6 Write tests for SERVICE_HUB_URL derivation: hub derives URLs, explicit overrides hub, MCM overrides .env, empty hub leaves defaults

## 4. Python Shared Authenticated httpx.AsyncClient

- [x] 4.1 Create factory function that returns `httpx.AsyncClient(auth=KeycloakAuth(...))` when remote with credentials, or `httpx.AsyncClient()` when local/no credentials
- [x] 4.2 Integrate into `TTSRemoteClient` — accept optional `httpx.AsyncClient` parameter, use shared client for requests
- [x] 4.3 Integrate into `EmbeddingClient` — accept optional `httpx.AsyncClient` parameter, use shared client for requests
- [x] 4.4 Integrate into `WhisperAPIProvider` — pass shared `httpx.AsyncClient` as `http_client` to `AsyncOpenAI` constructor
- [x] 4.5 Wire client creation in config sync handler — when auth credentials arrive and service_type is remote, create/update the session's shared client
- [x] 4.6 Write integration tests verifying auth header injection for TTS, STT, and embedding clients

## 5. MCM Tab Reorganization

- [x] 5.1 Restructure `talker_mcm.script` into 6 tabs (General, AI Model, Voice, Connection, Triggers, Debug) using MCM `subtab` pattern
- [x] 5.2 Add General tab settings: language, action_descriptions, female_gender, witness_distance, npc_speak_distance
- [x] 5.3 Add AI Model tab settings: ai_model_method, custom_ai_model, custom_ai_model_fast, use_reasoning, ai_base_url, openrouter_api_key, openai_api_key, ollama_base_url
- [x] 5.4 Add Voice tab settings: input_method, speak_key, stt_method, tts_enabled, tts_voice_method
- [x] 5.5 Add Connection tab with all sections: Service Type radio, Remote (hub URL, branch radio, custom branch), Local (service_url, service_ws_port), Auth (username, password, client_id, client_secret, ws_token), Advanced (llm_timeout, state_query_timeout)
- [x] 5.6 Add Triggers tab with General sub-section (time_gap, recent_speech_threshold, anti_spam_cd, speaker_pick_max_events) plus existing per-trigger sections
- [x] 5.7 Add Debug tab: debug_logging, reset controls
- [x] 5.8 Add new Connection field defaults to `config_defaults.lua`: service_type=0, service_hub_url="", branch=0, custom_branch="", auth_username="", auth_password="", auth_client_id="talker-client", auth_client_secret="", llm_timeout=60, state_query_timeout=10
- [x] 5.9 Add config getters in `interface/config.lua` for all new Connection fields
- [x] 5.10 Update `gamedata/configs/text/eng/talker_mcm.xml` with localization strings for new tabs, sections, and field descriptions

## 6. Lua WS URL Derivation

- [x] 6.1 Update `talker_ws_integration.script` URL construction — when service_type=Remote: derive WS URL from `service_hub_url` + `branch` (e.g., `wss://hub/ws/main`); when service_type=Local: use `service_url` or `ws://127.0.0.1:<port>/ws`
- [x] 6.2 Update `keycloak_client.lua` — skip ROPC when service_type is Local; only perform ROPC when Remote with non-empty auth credentials
- [x] 6.3 Update `config.sync` payload in `talker_ws_integration.script` to include all new Connection/auth fields
- [x] 6.4 Write Lua tests for URL derivation: local default, local custom URL, remote with hub+branch (main, dev, custom), remote without credentials

## 7. Verification & Documentation

- [x] 7.1 Run full Python test suite — verify no regressions
- [x] 7.2 Run full Lua test suite — verify no regressions
- [x] 7.3 Update `.env.example` with all new fields and comments
- [x] 7.4 Update `docs/Python_Service_Setup.md` with SERVICE_HUB_URL documentation and remote service usage instructions
