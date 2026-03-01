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

The config mirror SHALL provide typed access to configuration values, respecting server-side pins.

#### Scenario: Access model method (no pin)
- **WHEN** `config_mirror.get("model_method")` is called
- **AND** `model_method` is not pinned
- **THEN** the current MCM model_method value is returned

#### Scenario: Access model method (pinned)
- **WHEN** `config_mirror.get("model_method")` is called
- **AND** `model_method` is pinned to `3`
- **THEN** the pinned value `3` is returned regardless of MCM

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

The config mirror SHALL provide a way to dump current config state including pins.

#### Scenario: Dump config
- **WHEN** `config_mirror.dump()` is called
- **THEN** the full current config is returned as a dictionary

#### Scenario: Dump includes pins
- **WHEN** `config_mirror.dump()` is called
- **AND** pins are active
- **THEN** the dump includes a `pins` key showing all pinned field names and values

#### Scenario: HTTP endpoint for config
- **WHEN** `GET /debug/config` is requested
- **THEN** the current config including pins is returned as JSON
