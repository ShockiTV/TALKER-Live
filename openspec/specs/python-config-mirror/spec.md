# python-config-mirror

## Purpose

Python module that mirrors MCM configuration from Lua, providing typed access to settings for dialogue generation.

## Requirements

### Config storage

The config mirror SHALL store the latest MCM configuration received from Lua.

#### Scenario: Store config update
- **WHEN** a `config.update` message is received
- **THEN** the mirror replaces its stored config with the new values

#### Scenario: Store config sync
- **WHEN** a `config.sync` message is received
- **THEN** the mirror replaces its stored config with the new values

### Config access

The config mirror SHALL provide typed access to configuration values.

#### Scenario: Access model method
- **WHEN** `config_mirror.get("model_method")` is called
- **THEN** the current model_method value is returned

#### Scenario: Access with default
- **WHEN** `config_mirror.get("unknown_key", default=42)` is called
- **THEN** the default value `42` is returned

### Config validation

The config mirror SHALL validate incoming config against expected schema.

#### Scenario: Valid config accepted
- **WHEN** config with all expected fields is received
- **THEN** the config is stored without error

#### Scenario: Missing field warning
- **WHEN** config is missing an expected field
- **THEN** a warning is logged but config is still stored

### Change notification

The config mirror SHALL notify dependent modules when config changes.

#### Scenario: Notify on update
- **WHEN** config is updated
- **THEN** registered callbacks are invoked with the new config

#### Scenario: Register callback
- **WHEN** `config_mirror.on_change(callback)` is called
- **THEN** the callback is registered for future config changes

### Initial state

The config mirror SHALL start with sensible defaults until first sync.

#### Scenario: Default values available
- **WHEN** config mirror is accessed before any sync
- **THEN** default values are returned for all known settings

#### Scenario: Log waiting for sync
- **WHEN** service starts
- **THEN** the mirror logs "Waiting for config sync from game" at INFO level

### Config dump for debugging

The config mirror SHALL provide a way to dump current config state.

#### Scenario: Dump config
- **WHEN** `config_mirror.dump()` is called
- **THEN** the full current config is returned as a dictionary

#### Scenario: HTTP endpoint for config
- **WHEN** `GET /debug/config` is requested
- **THEN** the current config is returned as JSON
