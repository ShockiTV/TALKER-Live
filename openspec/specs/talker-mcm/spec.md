# talker-mcm

## Purpose

MCM (Mod Configuration Menu) integration for TALKER Expanded, providing user-configurable settings.

## Requirements

### MCM change callback

The talker_mcm module SHALL invoke a callback when any setting is changed by the user.

#### Scenario: Setting changed triggers callback
- **WHEN** user changes any MCM setting in the menu
- **THEN** the `on_mcm_changed` callback is invoked

#### Scenario: Callback publishes config
- **WHEN** `on_mcm_changed` callback is invoked
- **THEN** the full current config is collected and published via ZMQ

#### Scenario: Multiple changes batch
- **WHEN** user changes multiple settings in quick succession
- **THEN** each change triggers a separate config publish

### ZMQ port setting

The MCM SHALL include a setting for the ZMQ communication port.

#### Scenario: Default ZMQ port
- **WHEN** MCM is loaded without user customization
- **THEN** `zmq_port` defaults to `5555`

#### Scenario: Custom ZMQ port
- **WHEN** user sets `zmq_port` to `5560`
- **THEN** the ZMQ bridge uses port `5560` for binding
