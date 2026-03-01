## MODIFIED Requirements

### Requirement: Config sync scoped to session

When `config.sync` is received, the full config SHALL be applied only to the ConfigMirror for the session that sent the message. `handle_config_sync(payload, session_id)` SHALL accept a `session_id` parameter (defaulting to `"__default__"`). When a `SessionRegistry` has been set via `set_session_registry()`, it SHALL write to `registry.get_config(session_id)`. When no registry is set, it SHALL fall back to the global `config_mirror` singleton for backward compatibility.

#### Scenario: Config sync applies to correct session

- **WHEN** session "alice" sends `config.sync` with `model_method=1`
- **AND** session "bob" has `model_method=0`
- **THEN** alice's ConfigMirror SHALL have `model_method=1`
- **AND** bob's ConfigMirror SHALL remain `model_method=0`

#### Scenario: Config sync falls back to global mirror without registry

- **WHEN** no `SessionRegistry` has been set
- **AND** `handle_config_sync(payload)` is called without session_id
- **THEN** the global `config_mirror` singleton SHALL be updated

### Requirement: Config update scoped to session

When `config.update` is received, the setting change SHALL be applied only to the ConfigMirror for the session that sent the message. `handle_config_update(payload, session_id)` SHALL accept a `session_id` parameter (defaulting to `"__default__"`). Routing follows the same registry-or-fallback pattern as config sync.

#### Scenario: Config update applies to correct session

- **WHEN** session "alice" sends `config.update` with key `custom_ai_model`, value `gpt-4o`
- **THEN** alice's ConfigMirror SHALL reflect the updated model name
- **AND** other sessions' configs SHALL NOT change

## ADDED Requirements

### Requirement: Session registry injection for config handlers

The config handler module SHALL expose `set_session_registry(registry)` to inject a `SessionRegistry` instance. When set, `handle_config_sync` and `handle_config_update` SHALL route through the registry. When not set (None), they SHALL use the global `config_mirror` singleton.

#### Scenario: Registry injection enables per-session config

- **WHEN** `set_session_registry(registry)` is called with a SessionRegistry
- **AND** `handle_config_sync(payload, "alice")` is called
- **THEN** the config SHALL be written to `registry.get_config("alice")`
