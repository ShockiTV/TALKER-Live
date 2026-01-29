## ADDED Requirements

### Requirement: ZMQ subscriber initialization
The router SHALL initialize a ZMQ SUB socket connected to the Lua PUB endpoint.

#### Scenario: Connect to Lua publisher
- **WHEN** router starts
- **THEN** SUB socket connects to `tcp://127.0.0.1:5555`
- **THEN** socket subscribes to all topics (empty string filter)

#### Scenario: Configurable endpoint
- **WHEN** `LUA_PUB_ENDPOINT` environment variable is set
- **THEN** SUB socket connects to the specified endpoint instead of default

### Requirement: Topic-based handler registry
The router SHALL maintain a registry mapping topics to async handler functions.

#### Scenario: Register handler
- **WHEN** `router.on("game.event", handle_game_event)` is called
- **THEN** messages with topic `game.event` are routed to `handle_game_event`

#### Scenario: Multiple handlers
- **WHEN** handlers are registered for different topics
- **THEN** each message is routed to the correct handler based on topic

### Requirement: Async message processing
The router SHALL process incoming messages asynchronously without blocking.

#### Scenario: Process message
- **WHEN** a message `game.event {"type":"DEATH"}` is received
- **THEN** the router parses topic and JSON payload
- **THEN** the router calls the registered handler with the payload

#### Scenario: Non-blocking loop
- **WHEN** multiple messages arrive rapidly
- **THEN** the router processes them concurrently using asyncio

### Requirement: Message format parsing
The router SHALL parse messages in the format `<topic> <json-payload>`.

#### Scenario: Parse valid message
- **WHEN** message `config.update {"model_method":0}` is received
- **THEN** topic is extracted as `config.update`
- **THEN** payload is parsed as `{"model_method": 0}`

#### Scenario: Handle malformed message
- **WHEN** message cannot be parsed
- **THEN** the router logs an error and continues processing

### Requirement: FastAPI integration
The router SHALL run alongside FastAPI for HTTP health checks.

#### Scenario: Health endpoint available
- **WHEN** service is running
- **THEN** `GET /health` returns `{"status": "ok", "zmq_connected": true}`

#### Scenario: ZMQ runs in background
- **WHEN** FastAPI starts
- **THEN** ZMQ message loop runs as a background task

### Requirement: Graceful shutdown
The router SHALL handle shutdown signals cleanly.

#### Scenario: SIGINT shutdown
- **WHEN** SIGINT (Ctrl+C) is received
- **THEN** the router stops the message loop
- **THEN** ZMQ sockets are closed
- **THEN** the process exits cleanly

#### Scenario: SIGTERM shutdown
- **WHEN** SIGTERM is received
- **THEN** the router performs the same clean shutdown as SIGINT

### Requirement: Logging
The router SHALL log message receipt and processing for debugging.

#### Scenario: Log received messages
- **WHEN** a message is received
- **THEN** the router logs topic and timestamp at DEBUG level

#### Scenario: Log handler errors
- **WHEN** a handler raises an exception
- **THEN** the router logs the error at ERROR level and continues processing
