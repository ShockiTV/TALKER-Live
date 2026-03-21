# per-session-config

## Purpose

ConfigMirror keyed by session_id so each player has independent MCM settings and LLM client configuration.

## Requirements

### Requirement: Session registry manages per-session state

A `SessionRegistry` SHALL provide access to per-session `ConfigMirror` and `SpeakerSelector` instances. Calling `get_config(session_id)` SHALL return the ConfigMirror for that session, creating one with defaults if it does not exist. When creating a new ConfigMirror, it SHALL wire all callbacks previously registered via `on_any_config_change()` into the new mirror. Calling `get_speaker_selector(session_id)` SHALL return the SpeakerSelector for that session.

#### Scenario: First access creates default config

- **WHEN** `get_config("alice")` is called for a new session
- **THEN** a new `ConfigMirror` with default settings SHALL be created for "alice"
- **AND** subsequent calls with the same session_id SHALL return the same instance

#### Scenario: Different sessions have independent configs

- **WHEN** `get_config("alice")` and `get_config("bob")` are called
- **THEN** they SHALL return different `ConfigMirror` instances
- **AND** updating alice's config SHALL NOT affect bob's config

#### Scenario: Different sessions have independent speaker selectors

- **WHEN** `get_speaker_selector("alice")` and `get_speaker_selector("bob")` are called
- **THEN** they SHALL return different `SpeakerSelector` instances
- **AND** speaker cooldowns SHALL be independent between sessions

#### Scenario: New mirror inherits global callbacks

- **WHEN** `on_any_config_change(cb)` was registered before any sessions connect
- **AND** `get_config("new_player")` is called
- **THEN** the newly created ConfigMirror SHALL have `cb` in its `on_change` list

### Requirement: Config sync scoped to session

When `config.sync` is received, the full config SHALL be applied only to the ConfigMirror for the session that sent the message. `handle_config_sync(payload, session_id)` SHALL accept a `session_id` parameter (defaulting to `"__default__"`). When a `SessionRegistry` has been set via `set_session_registry()`, it SHALL write to `registry.get_config(session_id)`. When no registry is set, it SHALL fall back to the global `config_mirror` singleton for backward compatibility.

The config payload SHALL now include connection and auth fields: `service_type`, `service_hub_url`, `branch`, `custom_branch`, `auth_username`, `auth_password`, `auth_client_id`, `auth_client_secret`, `llm_timeout`, `state_query_timeout`. When auth credentials are present and `service_type` indicates remote, the session SHALL initialize or update its `KeycloakAuth` instance for outbound HTTP calls.

#### Scenario: Config sync applies to correct session

- **WHEN** session "alice" sends `config.sync` with `model_method=1`
- **AND** session "bob" has `model_method=0`
- **THEN** alice's ConfigMirror SHALL have `model_method=1`
- **AND** bob's ConfigMirror SHALL remain `model_method=0`

#### Scenario: Config sync falls back to global mirror without registry

- **WHEN** no `SessionRegistry` has been set
- **AND** `handle_config_sync(payload)` is called without session_id
- **THEN** the global `config_mirror` singleton SHALL be updated

#### Scenario: Config sync with local service type initializes KeycloakAuth

- **WHEN** session "alice" sends `config.sync` with `service_type=0` (Local), `auth_username="player1"`, `auth_password="secret"`, `auth_client_id="talker-client"`, `auth_client_secret="cs"`
- **THEN** alice's session SHALL have a `KeycloakAuth` instance configured with those credentials
- **AND** the session's shared `httpx.AsyncClient` SHALL use that `KeycloakAuth` for outbound requests
- **NOTE** Local service type means Python runs on the player's machine and must authenticate through the VPS Caddy reverse proxy

#### Scenario: Config sync with remote service type skips KeycloakAuth

- **WHEN** session "bob" sends `config.sync` with `service_type=1` (Remote)
- **THEN** bob's session SHALL NOT have a `KeycloakAuth` instance
- **AND** the session's shared `httpx.AsyncClient` SHALL have no `auth`
- **NOTE** Remote service type means Python runs on the VPS behind Caddy, so auth is handled at the proxy layer

### Requirement: Config update scoped to session

When `config.update` is received, the setting change SHALL be applied only to the ConfigMirror for the session that sent the message. `handle_config_update(payload, session_id)` SHALL accept a `session_id` parameter (defaulting to `"__default__"`). Routing follows the same registry-or-fallback pattern as config sync.

#### Scenario: Config update applies to correct session

- **WHEN** session "alice" sends `config.update` with key `custom_ai_model`, value `gpt-4o`
- **THEN** alice's ConfigMirror SHALL reflect the updated model name
- **AND** other sessions' configs SHALL NOT change

### Requirement: LLM client factory keyed by session

The LLM client factory function SHALL accept a `session_id` parameter and read from the session-specific ConfigMirror to determine `model_method` and `model_name`.

#### Scenario: Different sessions use different LLM providers

- **WHEN** alice's config has `model_method=0` (OpenAI)
- **AND** bob's config has `model_method=1` (OpenRouter)
- **THEN** `get_current_llm_client("alice")` SHALL return an OpenAI client
- **AND** `get_current_llm_client("bob")` SHALL return an OpenRouter client

### Requirement: Session registry injection for config handlers

The config handler module SHALL expose `set_session_registry(registry)` to inject a `SessionRegistry` instance. When set, `handle_config_sync` and `handle_config_update` SHALL route through the registry. When not set (None), they SHALL use the global `config_mirror` singleton.

#### Scenario: Registry injection enables per-session config

- **WHEN** `set_session_registry(registry)` is called with a SessionRegistry
- **AND** `handle_config_sync(payload, "alice")` is called
- **THEN** the config SHALL be written to `registry.get_config("alice")`

### Requirement: Session cleanup

The SessionRegistry SHALL support removing a session's state. When a session is removed, its ConfigMirror, SpeakerSelector, and any associated resources SHALL be released.

#### Scenario: Removed session state is garbage collected

- **WHEN** `remove_session("alice")` is called
- **THEN** alice's ConfigMirror and SpeakerSelector SHALL be removed
- **AND** subsequent `get_config("alice")` SHALL create a fresh default instance

### Requirement: ConfigMirror includes connection fields

The `ConfigMirror` model in `talker_service/src/talker_service/models/config.py` SHALL include the following new fields with defaults: `service_type` (int, default 0), `service_hub_url` (str, default ""), `branch` (int, default 0), `custom_branch` (str, default ""), `auth_username` (str, default ""), `auth_password` (str, default ""), `auth_client_id` (str, default "talker-client"), `auth_client_secret` (str, default ""), `llm_timeout` (int, default 60), `state_query_timeout` (int, default 10).

#### Scenario: ConfigMirror defaults include connection fields

- **WHEN** a new `ConfigMirror` is created with defaults
- **THEN** `service_type` SHALL be 0, `auth_client_id` SHALL be `"talker-client"`, `llm_timeout` SHALL be 60

#### Scenario: ConfigMirror stores auth credentials from sync

- **WHEN** `config.sync` includes `auth_username="player1"`
- **THEN** the ConfigMirror's `auth_username` field SHALL be `"player1"`

### Requirement: SERVICE_HUB_URL derives service URLs

The Python `Settings` class in `config.py` SHALL accept a `SERVICE_HUB_URL` environment variable. When set and per-service URLs (`tts_service_url`, `stt_endpoint`, `ollama_base_url`) are not explicitly configured, the hub URL SHALL derive them:
- `tts_service_url` = `{SERVICE_HUB_URL}/api/tts`
- `stt_endpoint` = `{SERVICE_HUB_URL}/api/stt/v1`
- `ollama_base_url` = `{SERVICE_HUB_URL}/api/embed`

Explicit per-service URLs SHALL always take precedence over derived URLs. MCM `service_hub_url` (via `config.sync`) SHALL override the `.env` `SERVICE_HUB_URL` when present.

#### Scenario: SERVICE_HUB_URL derives TTS URL

- **WHEN** `SERVICE_HUB_URL=https://talker-live.duckdns.org` is set in `.env`
- **AND** `TTS_SERVICE_URL` is not set
- **THEN** `settings.tts_service_url` SHALL be `"https://talker-live.duckdns.org/api/tts"`

#### Scenario: Explicit URL overrides derivation

- **WHEN** `SERVICE_HUB_URL=https://talker-live.duckdns.org` is set
- **AND** `TTS_SERVICE_URL=http://localhost:8100` is also set
- **THEN** `settings.tts_service_url` SHALL be `"http://localhost:8100"` (explicit wins)

#### Scenario: MCM hub URL overrides .env hub URL

- **WHEN** `.env` has `SERVICE_HUB_URL=https://default.example.com`
- **AND** `config.sync` includes `service_hub_url="https://custom.example.com"`
- **THEN** service URLs SHALL be derived from `https://custom.example.com`

#### Scenario: No hub URL leaves per-service defaults

- **WHEN** neither `SERVICE_HUB_URL` nor `service_hub_url` is configured
- **THEN** `tts_service_url`, `stt_endpoint`, and `ollama_base_url` SHALL use their individual defaults (empty or from `.env`)
