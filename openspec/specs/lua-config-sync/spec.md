# lua-config-sync

## Purpose

Lua module that collects MCM settings and publishes them to Python service for configuration synchronization.

## Requirements

### Full config collection

The config sync module SHALL collect all MCM settings into a single table for transmission.

#### Scenario: Collect all MCM settings
- **WHEN** `config_sync.collect_config()` is called
- **THEN** a table is returned containing all talker_mcm settings with their current values

### Config update publishing

The config sync module SHALL publish full config when any MCM setting changes.

#### Scenario: Publish on setting change
- **WHEN** any MCM setting is changed by the user
- **THEN** the module collects all settings and publishes with topic `config.update`

### Config sync on game load

The config sync module SHALL publish full config after game state is loaded.

#### Scenario: Sync after load
- **WHEN** game save is loaded and MCM is initialized
- **THEN** the module publishes full config with topic `config.sync` after a 1-second delay

#### Scenario: Delay prevents race condition
- **WHEN** game is loading
- **THEN** config sync waits 1 second to ensure MCM values are fully initialized

### Config payload structure

The config sync module SHALL include all AI-relevant settings in the payload.

#### Scenario: Payload contains model settings
- **WHEN** config is collected
- **THEN** payload includes `model_method`, `api_key`, `model_name` fields

#### Scenario: Payload contains behavior settings
- **WHEN** config is collected
- **THEN** payload includes `witness_distance`, `idle_conversation_cooldown`, `base_dialogue_chance` fields

#### Scenario: Payload contains feature flags
- **WHEN** config is collected
- **THEN** payload includes `enable_trigger_*` boolean fields for each trigger type
