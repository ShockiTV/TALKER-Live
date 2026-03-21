# per-session-config (delta)

## MODIFIED Requirements

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
