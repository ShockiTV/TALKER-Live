## 1. Python Service Setup

- [x] 1.1 Create `talker_service/` directory structure at project root
- [x] 1.2 Create `pyproject.toml` with project metadata and dependencies
- [x] 1.3 Create `requirements.txt` with pyzmq, fastapi, uvicorn, pydantic, loguru, python-dotenv
- [x] 1.4 Create `.env.example` with configuration template
- [x] 1.5 Create `run.py` entry point script
- [x] 1.6 Create `src/talker_service/__init__.py` and `__main__.py`

## 2. Python Config Module

- [x] 2.1 Create `src/talker_service/config.py` with pydantic-settings for service configuration
- [x] 2.2 Define default values for ZMQ endpoints, logging paths
- [x] 2.3 Support environment variable overrides

## 3. Python Pydantic Models

- [x] 3.1 Create `src/talker_service/models/__init__.py`
- [x] 3.2 Create `src/talker_service/models/messages.py` with BaseMessage, GameEventMessage, ConfigMessage schemas
- [x] 3.3 Create `src/talker_service/models/config.py` with MCM config mirror schema and defaults

## 4. Python ZMQ Router

- [x] 4.1 Create `src/talker_service/transport/__init__.py`
- [x] 4.2 Create `src/talker_service/transport/router.py` with ZMQRouter class
- [x] 4.3 Implement ZMQ SUB socket initialization connecting to `tcp://127.0.0.1:5555`
- [x] 4.4 Implement topic-based handler registry with `on(topic, handler)` method
- [x] 4.5 Implement async message loop with non-blocking receive
- [x] 4.6 Implement message parsing (topic + JSON payload)
- [x] 4.7 Implement graceful shutdown on SIGINT/SIGTERM

## 5. Python Handlers

- [x] 5.1 Create `src/talker_service/handlers/__init__.py`
- [x] 5.2 Create `src/talker_service/handlers/events.py` with game event logging handler
- [x] 5.3 Create `src/talker_service/handlers/config.py` with config mirror update handler
- [x] 5.4 Register handlers in main application startup

## 6. Python Config Mirror

- [x] 6.1 Implement config storage in `handlers/config.py`
- [x] 6.2 Implement `get(key, default)` accessor method
- [x] 6.3 Implement change notification callbacks
- [x] 6.4 Implement `dump()` method for debugging

## 7. Python FastAPI Integration

- [x] 7.1 Add FastAPI app creation in `__main__.py`
- [x] 7.2 Add `GET /health` endpoint returning ZMQ connection status
- [x] 7.3 Add `GET /debug/config` endpoint returning current config mirror
- [x] 7.4 Start ZMQ router as FastAPI background task on startup
- [x] 7.5 Configure uvicorn to run FastAPI on configurable port (default 8080)

## 8. Lua ZMQ Bridge

- [x] 8.1 Download libzmq.dll and place in `bin/pollnet/`
- [x] 8.2 Create `bin/lua/infra/zmq/` directory
- [x] 8.3 Create `bin/lua/infra/zmq/bridge.lua` with lzmq FFI binding
- [x] 8.4 Implement lazy initialization of ZMQ context and PUB socket
- [x] 8.5 Implement `publish(topic, payload)` function with JSON encoding
- [x] 8.6 Implement `is_connected()` status check function
- [x] 8.7 Implement `shutdown()` cleanup function
- [x] 8.8 Implement graceful error handling (log warning, set `is_available = false`)

## 9. Lua Event Publisher

- [x] 9.1 Create `bin/lua/infra/zmq/publisher.lua`
- [x] 9.2 Define topic constants (GAME_EVENT, PLAYER_DIALOGUE, CONFIG_UPDATE, etc.)
- [x] 9.3 Implement `send_game_event(event)` with character serialization
- [x] 9.4 Implement `send_player_dialogue(text, context)`
- [x] 9.5 Implement `send_heartbeat()`
- [x] 9.6 Ensure all publish functions are fire-and-forget (non-blocking)

## 10. Lua Config Sync

- [x] 10.1 Create config collection function in publisher module
- [x] 10.2 Implement `publish_config_update()` for MCM changes
- [x] 10.3 Implement `publish_config_sync()` for game load sync

## 11. MCM Integration

- [x] 11.1 Add `zmq_enabled` setting to `talker_mcm.script` (default: true)
- [x] 11.2 Add `zmq_port` setting to `talker_mcm.script` (default: 5555)
- [x] 11.3 Add `on_mcm_changed` callback that triggers config publish
- [x] 11.4 Update MCM UI definition with new settings

## 12. Persistence Integration

- [x] 12.1 Modify `talker_game_persistence.script` to call config sync on `load_state`
- [x] 12.2 Add 2-second delayed sync using `CreateTimeEvent`
- [x] 12.3 Add ZMQ bridge shutdown call in `on_game_end` callback

## 13. Trigger Integration

- [x] 13.1 Modify `bin/lua/interface/interface.lua` to add parallel ZMQ publish (via interface.lua, not trigger.lua)
- [x] 13.2 Call `zmq_integration.publish_game_event()` alongside existing `talker.register_event()`
- [x] 13.3 Ensure publish failure does not affect existing event flow

## 14. Heartbeat System

- [x] 14.1 Add heartbeat timer in Lua using `CreateTimeEvent` (5 second interval)
- [x] 14.2 Implement heartbeat handler in Python that logs last_seen timestamp
- [x] 14.3 Include heartbeat status in `/health` endpoint response

## 15. Startup Scripts

- [x] 15.1 Create `launch_talker_service.bat` for standalone service startup
- [x] 15.2 Document startup procedure in README
- [x] 15.3 Add service startup instructions to mod installation guide

## 16. Testing

- [x] 16.1 Create Python unit tests for ZMQ router message parsing
- [x] 16.2 Create Python unit tests for config mirror
- [x] 16.3 Manual integration test: start service, load game, verify events logged
- [x] 16.4 Manual integration test: change MCM setting, verify config received
- [x] 16.5 Manual integration test: game without service running, verify no errors

## 17. Documentation

- [x] 17.1 Update project README with Python service section
- [x] 17.2 Document ZMQ topic schema in design doc or separate file
- [x] 17.3 Document configuration options (environment variables, MCM settings)
- [x] 17.4 Update copilot-instructions.md with Python service architecture
