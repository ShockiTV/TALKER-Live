## MODIFIED Requirements

### Requirement: Config access

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

### Requirement: Config dump for debugging

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
