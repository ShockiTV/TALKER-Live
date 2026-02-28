# per-session-config

## Purpose

ConfigMirror keyed by session_id so each player has independent MCM settings and LLM client configuration.

## Requirements

### Requirement: Session registry manages per-session state

A `SessionRegistry` SHALL provide access to per-session `ConfigMirror` and `SpeakerSelector` instances. Calling `get_config(session_id)` SHALL return the ConfigMirror for that session, creating one with defaults if it does not exist. Calling `get_speaker_selector(session_id)` SHALL return the SpeakerSelector for that session.

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

### Requirement: Config sync scoped to session

When `config.sync` is received, the full config SHALL be applied only to the ConfigMirror for the session that sent the message. Other sessions' configs SHALL NOT be affected.

#### Scenario: Config sync applies to correct session

- **WHEN** session "alice" sends `config.sync` with `model_method=1`
- **AND** session "bob" has `model_method=0`
- **THEN** alice's ConfigMirror SHALL have `model_method=1`
- **AND** bob's ConfigMirror SHALL remain `model_method=0`

### Requirement: Config update scoped to session

When `config.update` is received, the setting change SHALL be applied only to the ConfigMirror for the session that sent the message.

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

### Requirement: Session cleanup

The SessionRegistry SHALL support removing a session's state. When a session is removed, its ConfigMirror, SpeakerSelector, and any associated resources SHALL be released.

#### Scenario: Removed session state is garbage collected

- **WHEN** `remove_session("alice")` is called
- **THEN** alice's ConfigMirror and SpeakerSelector SHALL be removed
- **AND** subsequent `get_config("alice")` SHALL create a fresh default instance
