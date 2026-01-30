# talker-persistence

## Purpose

Game save/load persistence for TALKER Expanded, including memory stores and configuration sync.

## Requirements

### Config sync on load

The persistence module SHALL trigger a config sync to Python after loading game state.

#### Scenario: Load triggers delayed sync
- **WHEN** `load_state(saved_data)` completes successfully
- **THEN** a delayed config sync is scheduled for 1 second later

#### Scenario: Sync uses config_sync module
- **WHEN** the delayed sync timer fires
- **THEN** `lua_config_sync.publish_full_config()` is called

#### Scenario: Load without Python service
- **WHEN** game is loaded but Python service is not running
- **THEN** the sync attempt fails silently (fire-and-forget)

### ZMQ shutdown on game end

The persistence module SHALL clean up ZMQ resources when the game ends.

#### Scenario: Shutdown on game end
- **WHEN** `on_game_end` callback is invoked
- **THEN** `zmq_bridge.shutdown()` is called to clean up resources

#### Scenario: Shutdown idempotent
- **WHEN** `zmq_bridge.shutdown()` is called multiple times
- **THEN** no errors occur (idempotent operation)
