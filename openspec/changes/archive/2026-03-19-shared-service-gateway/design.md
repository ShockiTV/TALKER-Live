## Context

Today, a player running `talker_service` locally can only use TTS, STT, and embedding services running on their own machine. The VPS at `talker-live.duckdns.org` runs these GPU-intensive services inside Docker (TTS on port 8100, faster-whisper-server on 8200, Ollama on 11434), but they're only accessible within the Docker network — there are no public HTTP routes for them.

The Caddy reverse proxy already handles JWT authentication for WebSocket connections using the `caddy-security` plugin and Keycloak JWKS validation (see `keycloak-auth` spec). The Docker Compose stack already has the services running and accessible internally. What's missing is:

1. **Caddy routes** to expose these services externally with JWT gating
2. **Python outbound auth** so `talker_service` can call the gateway-protected APIs when running locally
3. **MCM fields** to let the player configure which services to use (local vs. remote) and provide credentials
4. **MCM reorganization** — the current single-tab layout doesn't scale; adding Connection settings demands a proper tab structure

The auth infrastructure (Keycloak realm, ROPC flow, Lua `keycloak_client.lua`) already exists from the `keycloak-auth` capability. This design reuses it for Python outbound HTTP calls.

### Two Deployment Scenarios

**Scenario A — Full VPS (existing):** Lua connects to VPS via `wss://domain/ws/main?token=jwt`. Python runs on VPS inside Docker. Services are reached via Docker internal DNS (`http://tts-service:8100`). No outbound auth needed — services trust the internal network.

**Scenario B — Local Python + Remote Services (new):** Lua connects to local Python (`ws://127.0.0.1:5557/ws`, no token). MCM auth credentials flow via `config.sync` to Python. Python creates `KeycloakAuth` and calls remote APIs at `https://domain/api/tts/*`, `https://domain/api/stt/*`, `https://domain/api/embed/*` with JWT Bearer tokens.

## Goals / Non-Goals

**Goals:**
- Expose TTS, STT, and embedding services as JWT-authenticated HTTP APIs through Caddy
- Build a reusable `httpx.Auth` subclass for Python outbound HTTP authentication (ROPC grant, token caching, lazy init)
- Add MCM Connection tab with Local/Remote service type toggle, hub URL, branch selection, and auth fields
- Reorganize all MCM settings into 6 logical tabs (General, AI Model, Voice, Connection, Triggers, Debug)
- Enable per-request user logging via Caddy (JWT `sub` claim in access logs) for future rate limiting
- Whitelist Ollama endpoints to only `/api/embeddings` and `/api/tags` (no arbitrary model pulls)

**Non-Goals:**
- Neo4j / graph memory sharing — stays local per player. Multi-tenant graph is out of scope.
- Rate limiting implementation — we log user identity now, enforce limits later.
- MCM conditional field visibility (precondition-based hiding) — all fields shown flat with section headers. Conditional UX deferred to a future change.
- Token refresh via WebSocket — Python re-authenticates via ROPC when tokens expire (credentials always in memory from `config.sync`).
- New Docker services — all containers already exist in the compose stack. No new images needed.

## Decisions

### Decision 1: Caddy as Transparent API Gateway

**Choice:** Add 3 new `route` blocks in Caddyfile that JWT-gate and reverse-proxy to existing internal services.

**Alternatives considered:**
- *Dedicated API gateway (Kong, Traefik)*: Overkill — Caddy already handles JWT validation for WS routes. Adding 3 more route blocks is trivial.
- *Python-level auth middleware*: Would require each service to validate JWTs independently. Caddy centralizes auth at the edge.

**Routes:**
- `/api/tts/*` → `tts-service:8100` (strip `/api/tts` prefix)
- `/api/stt/*` → `stt-service:8200` (strip `/api/stt` prefix, note: whisper-server expects `/v1/audio/transcriptions`)
- `/api/embed/*` → `ollama:11434` (strip `/api/embed` prefix, but with path whitelist — see Decision 2)

All routes require valid JWT with `player` role, inject `X-Player-ID` from `sub` claim, and log requests for future rate limiting.

### Decision 2: Ollama Endpoint Whitelist

**Choice:** Only allow `/api/embed/api/embeddings` and `/api/embed/api/tags` through Caddy. All other Ollama paths return 403.

**Rationale:** Ollama exposes admin endpoints like `/api/pull` (download models), `/api/delete`, `/api/create`. Whitelisting prevents abuse — players can only generate embeddings and check available models.

**Implementation:** Caddy `route /api/embed/*` block uses nested `@matcher` with `path` matching. Non-whitelisted paths get `respond 403`.

### Decision 3: KeycloakAuth httpx.Auth Subclass

**Choice:** New `talker_service/src/talker_service/auth/keycloak.py` module with an `httpx.Auth` subclass.

**Behavior:**
1. **Lazy init**: No token fetched until the first HTTP request. Credentials come from `config.sync` (which may arrive seconds after startup).
2. **ROPC grant**: POST to `{token_url}/realms/talker/protocol/openid-connect/token` with `grant_type=password`, `client_id`, `client_secret`, `username`, `password`.
3. **Token caching**: Store `access_token` and `refresh_token` with their expiry timestamps. Reuse until expired.
4. **Proactive refresh**: If `access_token` has expired but `refresh_token` is still valid, use `grant_type=refresh_token` first.
5. **Re-ROPC fallback**: If both tokens are expired, do a fresh ROPC grant (credentials are always in memory).
6. **401 retry**: If the server returns 401 despite a cached token, clear the cache and retry once with a fresh token.
7. **No auth when local**: If `service_type` is "local" or credentials are empty, the auth object is `None` and httpx calls go unauthenticated. This is the default for Docker-internal calls.

**Alternatives considered:**
- *OAuth2 client credentials grant*: Simpler, but doesn't provide per-user identity. We want `sub` claim to track which player is making requests.
- *Pre-fetched token passed as header*: Would require manual refresh logic scattered across clients. `httpx.Auth` centralizes it.
- *Shared singleton vs per-session auth*: Auth instance is **per-session** because each player has their own credentials (from their own `config.sync`). The `SessionRegistry` manages lifecycle.

### Decision 4: SERVICE_HUB_URL for URL Derivation

**Choice:** Single `.env` variable `SERVICE_HUB_URL` (e.g., `https://talker-live.duckdns.org`) that derives all API URLs.

**Derivation rules (Python config.py):**
- `tts_service_url` = `{SERVICE_HUB_URL}/api/tts` (if not explicitly set)
- `stt_endpoint` = `{SERVICE_HUB_URL}/api/stt/v1` (if not explicitly set)
- `ollama_base_url` = `{SERVICE_HUB_URL}/api/embed` (if not explicitly set)
- `keycloak_token_url` = `{SERVICE_HUB_URL}/auth` (if not explicitly set)

Explicit per-service URLs always take precedence. `SERVICE_HUB_URL` is a convenience for the common case where all services are behind one domain.

**Why not MCM:** This is a Python-side `.env` setting, not an MCM field. Players running local Python don't need to configure this in-game — they set it once in their `.env` file. The MCM `service_hub_url` field exists for the Connection tab but flows via `config.sync` to override the `.env` default.

**Wait — clarification:** MCM **does** have `service_hub_url` as a field in the Connection tab. When the player sets it in MCM and service_type is "remote", it flows via `config.sync` to Python and overrides the `.env` default. The `.env` `SERVICE_HUB_URL` is the fallback for VPS deployments (Scenario A) where no MCM config arrives.

### Decision 5: MCM Credential Flow

**Choice:** MCM `auth_username`, `auth_password`, `auth_client_id`, `auth_client_secret` are the single source of truth. They flow to both Lua (WS auth) and Python (HTTP API auth) via `config.sync`.

**Flow:**
1. Player enters credentials in MCM Connection tab
2. On game load, `config.sync` sends all MCM values to Python (including auth fields)
3. Python `ConfigMirror` stores them. On first outbound HTTP call, `KeycloakAuth` reads them and does ROPC.
4. Lua uses the same credentials for WS authentication (existing `keycloak_client.lua` flow)

**Key insight:** Lua and Python never need auth simultaneously in Scenario B. Lua connects locally (no auth), Python calls remote APIs (needs auth). In Scenario A, Python runs on VPS (no outbound auth needed), and Lua sends JWT via WS token parameter.

### Decision 6: MCM 6-Tab Reorganization

**Choice:** Split the current flat layout into 6 tabs.

| Tab | Settings |
|-----|----------|
| **General** | language, action_descriptions, female_gender, witness_distance, npc_speak_distance |
| **AI Model** | ai_model_method, custom_ai_model, custom_ai_model_fast, use_reasoning, ai_base_url, openrouter_api_key, openai_api_key, ollama_base_url |
| **Voice** | input_method, speak_key, stt_method, tts_enabled, tts_voice_method |
| **Connection** | service_type (Local/Remote), service_hub_url, branch (main/dev/custom), custom_branch, service_url, auth_username, auth_password, auth_client_id, auth_client_secret, llm_timeout, state_query_timeout |
| **Triggers** | [General sub-section: time_gap, recent_speech_threshold, anti_spam_cd, speaker_pick_max_events] + existing per-trigger toggles and sliders |
| **Debug** | debug_logging, reset buttons |

**All fields always visible** — no conditional `precondition` hiding for now. Section headers (`--` separator lines from MCM framework) group related fields within tabs.

### Decision 7: Lua Skips ROPC for Local Service Type

**Choice:** When MCM `service_type` is "local" (the default), `keycloak_client.lua` skips ROPC entirely. The WS connect URL has no `?token=` parameter.

**Rationale:** Local connections go to `ws://127.0.0.1:5557/ws` — no Caddy, no JWT needed. ROPC only makes sense when connecting to a remote service behind Caddy.

### Decision 8: Shared httpx.AsyncClient with Auth

**Choice:** A single `httpx.AsyncClient` per session, created with `auth=KeycloakAuth(...)` when remote, or `auth=None` when local. This client is injected into `TTSRemoteClient`, `EmbeddingClient`, and the OpenAI SDK (via `http_client` parameter).

**STT special case:** The OpenAI SDK used by `WhisperAPIProvider` accepts an `http_client` parameter. We pass `httpx.AsyncClient(auth=keycloak_auth)` which intercepts all requests and adds the Bearer token. The SDK's default `Authorization: Bearer <api_key>` header gets overwritten by the auth hook.

## Risks / Trade-offs

### [Risk] Token expiry during long gameplay sessions → Mitigation: proactive refresh + re-ROPC
The `KeycloakAuth` subclass proactively refreshes tokens before expiry. If the refresh token also expires (default Keycloak: 30 min idle), it falls back to a full ROPC grant. Since credentials are always in memory, this is transparent. Worst case: one extra HTTP roundtrip on the first request after a long pause.

### [Risk] MCM tab restructure breaks existing player configs → Mitigation: same MCM keys, additive changes
MCM settings are keyed by string ID, not by tab position. Moving a setting between tabs doesn't change its stored value. New fields (`service_type`, `service_hub_url`, `branch`, etc.) have sensible defaults that preserve current behavior (service_type=local, branch=main).

### [Risk] Ollama whitelist too restrictive → Mitigation: only 2 endpoints needed
`TTSRemoteClient` calls `/generate`, STT calls `/v1/audio/transcriptions`, and embeddings call `/api/embeddings`. The only Ollama endpoints actually used are `/api/embeddings` (generate) and `/api/tags` (health check). If future features need more Ollama endpoints, the Caddy whitelist is a one-line change.

### [Risk] SERVICE_HUB_URL + MCM service_hub_url precedence confusion → Mitigation: clear override chain
Precedence: MCM value (via config.sync) > `.env` SERVICE_HUB_URL > empty (disabled). Document this in `.env.example` and MCM tooltip text.

### [Trade-off] All MCM fields visible vs. conditional hiding
Showing all Connection fields even when service_type is "local" adds visual noise. But the MCM `precondition` system is untested with this many fields and could cause subtle bugs. We accept the clutter now and revisit conditional hiding when we have more MCM experience.

### [Trade-off] Per-session KeycloakAuth vs. global singleton
Each connected player gets their own `KeycloakAuth` instance with their own token cache. This is correct for multi-player VPS scenarios but adds memory overhead. For the common single-player case, there's only one session so the overhead is negligible.

## Open Questions

1. **Keycloak token endpoint path**: Is it `{hub}/auth/realms/talker/protocol/openid-connect/token` or does Caddy strip `/auth` before proxying? Need to verify against the current Caddyfile route.

2. **STT endpoint path convention**: The faster-whisper-server expects `/v1/audio/transcriptions`. With Caddy stripping `/api/stt`, the client would call `{hub}/api/stt/v1/audio/transcriptions`. Verify this maps correctly after prefix strip.
