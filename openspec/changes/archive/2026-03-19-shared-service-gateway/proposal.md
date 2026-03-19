## Why

Players who run talker_service locally (with their own LLM keys) currently cannot use the VPS-hosted TTS, STT, and embedding services. These GPU-intensive services are expensive to self-host and most players don't have the hardware. Exposing them as authenticated HTTP APIs through Caddy lets local players consume shared infrastructure while keeping their LLM orchestration local.

The MCM settings page is also overdue for reorganization — all ~30 settings are crammed into a single "General" tab, making it hard to navigate. The new Connection section (with Local/Remote service type, auth fields, branch selection) needs a proper home, and existing settings benefit from logical grouping.

## What Changes

- **Caddy API routes**: Add JWT-gated reverse proxy routes for TTS (`/api/tts/*`), STT (`/api/stt/*`), and embeddings (`/api/embed/*` — whitelisted to `/api/embeddings` and `/api/tags` only)
- **Python KeycloakAuth**: New `httpx.Auth` subclass that performs ROPC token exchange using credentials received via `config.sync`, with lazy init, token caching, and proactive refresh
- **Python SERVICE_HUB_URL**: New `.env` setting that, when set, derives TTS/STT/embed API URLs from the hub and enables authenticated outbound HTTP calls
- **Auth credential flow**: MCM `auth_*` fields become the single source of truth — credentials flow via `config.sync` to Python, which uses them for both WS auth (existing) and HTTP API auth (new)
- **MCM reorganization**: Split the flat General tab into 6 logical tabs: General, AI Model, Voice, Connection, Triggers (with new General sub-section), Debug
- **Connection tab**: Service Type toggle (Local/Remote), Remote section (hub URL, branch with main/dev/custom, custom branch text), Local section (service URL), Auth section (username, password, client ID, client secret), Advanced section (LLM timeout, state query timeout)
- **Per-request user logging**: Caddy logs the JWT `sub` claim on all API requests for future rate-limiting and usage tracking

## Capabilities

### New Capabilities
- `service-api-gateway`: Caddy routes exposing TTS/STT/embed as JWT-authenticated HTTP APIs with Ollama endpoint whitelisting and per-user request logging
- `python-keycloak-auth`: httpx.Auth subclass for outbound HTTP authentication — ROPC grant, token caching, lazy init from config.sync credentials, proactive refresh, 401 retry
- `mcm-tab-layout`: Reorganize MCM into 6 tabs (General, AI Model, Voice, Connection, Triggers, Debug) with Connection tab containing Local/Remote service type, branch selection, and auth fields

### Modified Capabilities
- `service-token-auth`: Auth credentials now flow from MCM via config.sync to Python for HTTP API calls (not just WS auth). Lua skips ROPC when service type is Local.
- `talker-mcm`: Settings restructured from flat General tab into multiple tabs. New fields: service_type, service_hub_url, branch, custom_branch. Trigger general settings (time_gap, anti_spam_cd, recent_speech_threshold, speaker_pick_max_events) move under Triggers > General.
- `per-session-config`: ConfigMirror receives new connection fields (service_type, service_hub_url, branch, custom_branch). Python uses auth_* credentials from config to initialize KeycloakAuth for outbound HTTP.

## Impact

- **Caddy config** (`docs/deploy/Caddyfile`): 3 new route blocks
- **Python transport** (`talker_service/src/talker_service/`): New `auth/keycloak.py` module; modifications to `config.py`, `__main__.py`, `tts/remote.py`, `storage/embedding.py`, `stt/whisper_api.py` to accept shared authenticated httpx client
- **Python models** (`models/config.py`): New fields for connection settings
- **Lua MCM** (`gamedata/scripts/talker_mcm.script`): Full restructure into tabs
- **Lua config** (`bin/lua/interface/config.lua`, `config_defaults.lua`): New getters for connection fields
- **Lua auth** (`bin/lua/infra/auth/keycloak_client.lua`): Skip ROPC when service_type is local
- **Lua WS integration** (`gamedata/scripts/talker_ws_integration.script`): URL derivation based on service_type (local: use service_url directly; remote: derive from hub + branch)
- **MCM localization** (`gamedata/configs/text/eng/talker_mcm.xml`): New strings for tabs and connection fields
- **Docker compose** (`docs/deploy/docker-compose.yml`): No changes needed (services already exposed internally)
- **`.env.example`**: New `SERVICE_HUB_URL` field (uncommented with default)
