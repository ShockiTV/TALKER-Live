# session-global-callbacks

## Purpose

Allow shared-resource initialization callbacks (STT provider, TTS volume sync) to fire when *any* session's ConfigMirror is synced or updated, regardless of session ID.

## ADDED Requirements

### Requirement: SessionRegistry supports global config callbacks

`SessionRegistry` SHALL expose an `on_any_config_change(callback)` method that stores callbacks to be fired when any per-session `ConfigMirror` triggers `on_change`. The stored callbacks SHALL be wired into every `ConfigMirror` created by `get_config()`.

#### Scenario: Global callback fires on first session config sync

- **WHEN** `session_registry.on_any_config_change(my_callback)` is registered at startup
- **AND** session "__default__" sends `config.sync` for the first time
- **THEN** `my_callback` SHALL be called with the synced config snapshot

#### Scenario: Global callback fires from any session

- **WHEN** `on_any_config_change(my_callback)` is registered
- **AND** session "alice" sends `config.sync`
- **THEN** `my_callback` SHALL be called
- **AND** when session "bob" sends `config.sync`, `my_callback` SHALL also be called

#### Scenario: Multiple global callbacks registered

- **WHEN** `on_any_config_change(cb_a)` and `on_any_config_change(cb_b)` are both registered
- **AND** any session syncs config
- **THEN** both `cb_a` and `cb_b` SHALL be called

### Requirement: Global callbacks wired at mirror creation time

When `get_config(session_id)` creates a new `ConfigMirror`, it SHALL call `mirror.on_change(cb)` for every callback previously registered via `on_any_config_change()`. This ensures that even lazily-created mirrors inherit all global callbacks.

#### Scenario: Late session gets global callbacks

- **WHEN** `on_any_config_change(init_stt)` is registered during startup
- **AND** a new WS client connects 5 minutes later with session "late_player"
- **THEN** `get_config("late_player")` SHALL create a mirror with `init_stt` already wired
- **AND** when "late_player" syncs config, `init_stt` SHALL fire

#### Scenario: Existing mirror not affected by later registrations

- **WHEN** `get_config("early")` is called before any global callbacks are registered
- **AND** `on_any_config_change(new_cb)` is registered afterwards
- **THEN** "early"'s mirror SHALL NOT have `new_cb` (callbacks are wired only at creation time)

### Requirement: STT init callback registered via global callbacks

`__main__.py` SHALL register `_init_stt_on_config` on `session_registry.on_any_config_change()` instead of `config_mirror.on_change()`. The existing `_stt_initialised` guard SHALL remain to prevent duplicate initialization.

#### Scenario: STT provider created on first config sync

- **WHEN** the service starts and a client sends `config.sync` with `stt_method=1` (API)
- **THEN** `_init_stt_on_config` SHALL fire
- **AND** `set_stt_provider()` SHALL be called with a valid STT provider
- **AND** subsequent mic audio chunks SHALL be transcribed successfully

#### Scenario: STT init does not repeat

- **WHEN** `_init_stt_on_config` has already fired once (setting `_stt_initialised = True`)
- **AND** another session syncs config
- **THEN** `_init_stt_on_config` SHALL return early without creating a second provider

### Requirement: TTS volume callback registered via global callbacks

`__main__.py` SHALL register the TTS volume-boost callback on `session_registry.on_any_config_change()` instead of `config_mirror.on_change()`.

#### Scenario: TTS volume updated on config sync

- **WHEN** the service starts and a client sends `config.sync` with a `tts_volume_boost` value
- **THEN** the TTS volume callback SHALL fire and update the TTS engine's volume setting
